"""Client XMLRPC per il flowgraph.

Permette di cambiare frequenza, guadagni, PPM e offset senza fermare la
catena. Gli stessi parametri possono essere scritti anche da telive (sintonia
automatica, correzione PPM, scansione): per questo la GUI mostra i valori
*letti* dal ricevitore, non quelli digitati.

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import xmlrpc.client
from dataclasses import dataclass

#: Timeout breve: la GUI interroga il ricevitore una volta al secondo e non
#: deve mai bloccarsi se il flowgraph è occupato o appena terminato.
DEFAULT_TIMEOUT = 2.0


class _Transport(xmlrpc.client.Transport):
    """Transport con timeout: quello di default non ne ha."""

    def __init__(self, timeout: float):
        super().__init__()
        self._timeout = timeout

    def make_connection(self, host):
        conn = super().make_connection(host)
        conn.timeout = self._timeout
        return conn


@dataclass
class RxStatus:
    """Fotografia dello stato del ricevitore."""

    reachable: bool
    name: str = ""
    channels: int = 0
    freq_hz: float = 0.0
    samp_rate: float = 0.0
    ppm: float = 0.0
    gain: float = 0.0
    offsets_hz: list[float] | None = None
    error: str = ""


class ReceiverControl:
    """Wrapper attorno al server XMLRPC del flowgraph.

    Ogni chiamata può fallire (ricevitore non ancora avviato, appena fermato):
    i metodi non sollevano eccezioni di rete, restituiscono ``False``/``None``
    e lasciano decidere al chiamante.
    """

    def __init__(self, port: int, host: str = "127.0.0.1",
                 timeout: float = DEFAULT_TIMEOUT):
        self.host = host
        self.port = port
        self.url = f"http://{host}:{port}/"
        self._proxy = xmlrpc.client.ServerProxy(
            self.url, allow_none=True, transport=_Transport(timeout)
        )

    # -- primitive --------------------------------------------------------

    def _call(self, method: str, *args):
        try:
            return getattr(self._proxy, method)(*args)
        except Exception:
            # OSError, xmlrpc.client.Fault, http.client.*: per il chiamante
            # sono tutti lo stesso caso, "il ricevitore non risponde".
            return None

    def is_alive(self) -> bool:
        return self._call("get_freq") is not None

    # -- parametri modificabili a caldo -----------------------------------

    def set_freq(self, hz: float) -> bool:
        return self._call("set_freq", float(hz)) is not None

    def set_gain(self, value: float) -> bool:
        return self._call("set_sdr_gain", float(value)) is not None

    def set_if_gain(self, value: float) -> bool:
        return self._call("set_sdr_ifgain", float(value)) is not None

    def set_bb_gain(self, value: float) -> bool:
        return self._call("set_sdr_bbgain", float(value)) is not None

    def set_ppm(self, value: float) -> bool:
        return self._call("set_ppm_corr", float(value)) is not None

    def set_lowpass(self, hz: float) -> bool:
        return self._call("set_options_low_pass", float(hz)) is not None

    def set_channel_offset(self, channel: int, hz: float) -> bool:
        """Imposta l'offset del canale ``channel`` (1-based)."""
        return self._call(f"set_xlate_offset{int(channel)}", float(hz)) is not None

    def get_channel_offset(self, channel: int):
        return self._call(f"get_xlate_offset{int(channel)}")

    # -- stato ------------------------------------------------------------

    def status(self) -> RxStatus:
        freq = self._call("get_freq")
        if freq is None:
            return RxStatus(reachable=False, error="ricevitore non raggiungibile")

        channels = self._call("get_telive_receiver_channels") or 0
        offsets = []
        for i in range(1, int(channels) + 1):
            value = self._call(f"get_xlate_offset{i}")
            offsets.append(float(value) if value is not None else 0.0)

        return RxStatus(
            reachable=True,
            name=self._call("get_telive_receiver_name") or "",
            channels=int(channels),
            freq_hz=float(freq),
            samp_rate=float(self._call("get_samp_rate") or 0.0),
            ppm=float(self._call("get_ppm_corr") or 0.0),
            gain=float(self._call("get_sdr_gain") or 0.0),
            offsets_hz=offsets,
        )

    def apply_config(self, cfg) -> bool:
        """Riallinea il ricevitore ai parametri "a caldo" della configurazione.

        Numero di canali, porte e sorgente non sono modificabili a caldo:
        richiedono un riavvio della catena.
        """
        ok = True
        ok &= self.set_freq(cfg.sdr.freq_hz)
        ok &= self.set_gain(cfg.sdr.gain)
        ok &= self.set_if_gain(cfg.sdr.if_gain)
        ok &= self.set_bb_gain(cfg.sdr.bb_gain)
        ok &= self.set_ppm(cfg.sdr.ppm)
        ok &= self.set_lowpass(cfg.sdr.lowpass_hz)
        for idx, ch in cfg.active_channels:
            ok &= self.set_channel_offset(idx, ch.offset_hz)
        return ok
