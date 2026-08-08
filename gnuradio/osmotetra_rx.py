#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ricevitore TETRA multicanale headless per la catena telive.

Flowgraph GNU Radio 3.10 parametrico, derivato dai flowgraph
``telive_1ch_gr310_udp_xmlrpc_headless.py`` e
``telive_6ch_gr310_udp_xmlrpc_headless.py`` di Jacek Lipkowski SQ5BPF, che
avevano tutti i parametri cablati nel sorgente.

Per ciascun canale N (1..6) la catena è::

    osmosdr_source ──┬─► freq_xlating_fir_filter_ccc(offset_N)
                     │      └─► agc3_cc ─► mmse_resampler_cc ─► udp_sink(base+N)
                     └─► ... (un ramo per canale)

Il server XMLRPC in ascolto su ``base_port`` espone i nomi di variabile che
telive si aspetta di trovare (``telive_receiver_name``,
``telive_receiver_channels``, ``freq``, ``samp_rate``, ``ppm_corr``,
``sdr_gain``, ``xlate_offsetN``): senza di essi telive disabilita il controllo
del ricevitore e le funzioni di scansione e sintonia automatica.

Attenzione: le porte UDP e il server XMLRPC sono fissati alla costruzione del
flowgraph e non sono modificabili a caldo — cambiarli richiede un riavvio.
Frequenza, guadagni, PPM e offset si cambiano invece via XMLRPC senza fermare
nulla.

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import os
import signal
import sys
import threading
from xmlrpc.server import SimpleXMLRPCServer

from gnuradio import analog, blocks, filter, gr, network
from gnuradio.filter import firdes

try:
    import osmosdr
except ImportError:  # pragma: no cover - dipende dall'ambiente
    osmosdr = None

MAX_CHANNELS = 6
#: Frequenza di campionamento attesa da simdemod3_py3.py a valle.
DEFAULT_OUT_RATE = 36000
#: Dimensione del datagramma usata dai flowgraph upstream.
UDP_PACKET_SIZE = 1472


class OsmoTetraRX(gr.top_block):
    """Ricevitore a N canali con uscita UDP e controllo XMLRPC."""

    def __init__(self, opts):
        gr.top_block.__init__(self, "OsmoTetra RX", catch_exceptions=True)

        self.channels = opts.channels
        self.samp_rate = float(opts.samp_rate)
        self.first_decim = int(opts.first_decim)
        self.out_sample_rate = int(opts.out_rate)
        self.options_low_pass = float(opts.lowpass)
        self.freq = float(opts.freq)
        self.ppm_corr = float(opts.ppm)
        self.sdr_gain = float(opts.gain)
        self.sdr_ifgain = float(opts.if_gain)
        self.sdr_bbgain = float(opts.bb_gain)
        self.first_port = int(opts.base_port)
        self.udp_dest_addr = opts.udp_host
        self.udp_packet_size = UDP_PACKET_SIZE

        # Lette da telive via XMLRPC per riconoscere il tipo di ricevitore.
        self.telive_receiver_name = opts.rx_name
        self.telive_receiver_channels = self.channels

        self.if_samp_rate = self.samp_rate / self.first_decim

        # Un offset (e un offset "fine", usato da telive per la correzione
        # AFC) per canale. Gli indici pubblici partono da 1, come in telive.
        self._offsets = list(opts.offsets)
        self._fine_offsets = [0.0] * self.channels

        self._xlating = []
        self._resamplers = []
        self._udp_sinks = []

        self._build(opts)
        self._start_xmlrpc(opts)

    # -- costruzione ------------------------------------------------------

    def _make_source(self, opts):
        """Crea il blocco sorgente secondo ``--source``.

        Oltre a ``osmosdr`` sono disponibili ``file:<percorso>`` e ``null``,
        che permettono di provare l'intera catena (e il controllo XMLRPC)
        senza avere una radio collegata.
        """
        spec = opts.source
        if spec == "null":
            src = blocks.null_source(gr.sizeof_gr_complex)
            thr = blocks.throttle(gr.sizeof_gr_complex, self.samp_rate, True)
            self.connect(src, thr)
            self._source_ctl = None
            return thr

        if spec.startswith("file:"):
            path = spec[len("file:"):]
            if not os.path.isfile(path):
                raise SystemExit(f"file IQ non trovato: {path}")
            src = blocks.file_source(gr.sizeof_gr_complex, path, opts.repeat)
            # Senza throttle un file locale viene consumato a velocità di
            # I/O e i datagrammi UDP a valle vengono persi.
            thr = blocks.throttle(gr.sizeof_gr_complex, self.samp_rate, True)
            self.connect(src, thr)
            self._source_ctl = None
            return thr

        if spec != "osmosdr":
            raise SystemExit(f"sorgente non riconosciuta: {spec}")

        if osmosdr is None:
            raise SystemExit(
                "modulo osmosdr non disponibile: installa gr-osmosdr\n"
                "  sudo apt-get install gr-osmosdr"
            )

        src = osmosdr.source(args="numchan=1 " + opts.device_args)
        src.set_time_unknown_pps(osmosdr.time_spec_t())
        src.set_sample_rate(self.samp_rate)
        src.set_center_freq(self.freq, 0)
        src.set_freq_corr(self.ppm_corr, 0)
        src.set_dc_offset_mode(0, 0)
        src.set_iq_balance_mode(0, 0)
        src.set_gain_mode(False, 0)
        src.set_gain(self.sdr_gain, 0)
        src.set_if_gain(self.sdr_ifgain, 0)
        src.set_bb_gain(self.sdr_bbgain, 0)
        src.set_antenna(opts.antenna, 0)
        src.set_bandwidth(opts.bandwidth, 0)
        self._source_ctl = src
        return src

    def _taps(self):
        return firdes.low_pass(
            1, self.samp_rate, self.options_low_pass, self.options_low_pass * 0.2
        )

    def _build(self, opts):
        source = self._make_source(opts)
        taps = self._taps()
        ratio = float(self.if_samp_rate) / float(self.out_sample_rate)

        for idx in range(self.channels):
            xlate = filter.freq_xlating_fir_filter_ccc(
                self.first_decim, taps,
                self._offsets[idx] + self._fine_offsets[idx],
                self.samp_rate,
            )
            agc = analog.agc3_cc(1e-3, 1e-4, 1.0, 1.0, 1)
            agc.set_max_gain(65536)
            resamp = filter.mmse_resampler_cc(0, ratio)
            sink = network.udp_sink(
                gr.sizeof_gr_complex, 1,
                self.udp_dest_addr, self.first_port + 1 + idx,
                0, self.udp_packet_size, False,
            )

            self.connect(source, xlate)
            self.connect(xlate, agc)
            self.connect(agc, resamp)
            self.connect(resamp, sink)

            self._xlating.append(xlate)
            self._resamplers.append(resamp)
            self._udp_sinks.append(sink)

    # -- XMLRPC -----------------------------------------------------------

    def _start_xmlrpc(self, opts):
        # I flowgraph upstream ascoltano su 0.0.0.0; qui il default è
        # loopback, perché telive e la GUI girano sulla stessa macchina.
        self.xmlrpc_server = SimpleXMLRPCServer(
            (opts.xmlrpc_bind, self.first_port), allow_none=True, logRequests=False
        )
        self.xmlrpc_server.register_instance(self)
        self._xmlrpc_thread = threading.Thread(
            target=self.xmlrpc_server.serve_forever, daemon=True
        )
        self._xmlrpc_thread.start()

    def stop(self):
        try:
            self.xmlrpc_server.shutdown()
        except Exception:  # pragma: no cover - best effort in fase di uscita
            pass
        return gr.top_block.stop(self)

    # -- accessori esposti via XMLRPC -------------------------------------
    #
    # telive interroga e imposta queste variabili per nome: i nomi dei
    # metodi sono parte dell'interfaccia e non vanno cambiati.

    def get_telive_receiver_name(self):
        return self.telive_receiver_name

    def get_telive_receiver_channels(self):
        return self.telive_receiver_channels

    def get_freq(self):
        return self.freq

    def set_freq(self, freq):
        self.freq = float(freq)
        if self._source_ctl is not None:
            self._source_ctl.set_center_freq(self.freq, 0)

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = float(samp_rate)
        self.set_if_samp_rate(self.samp_rate / self.first_decim)
        taps = self._taps()
        for xlate in self._xlating:
            xlate.set_taps(taps)
        if self._source_ctl is not None:
            self._source_ctl.set_sample_rate(self.samp_rate)

    def get_if_samp_rate(self):
        return self.if_samp_rate

    def set_if_samp_rate(self, if_samp_rate):
        self.if_samp_rate = float(if_samp_rate)
        ratio = float(self.if_samp_rate) / float(self.out_sample_rate)
        for resamp in self._resamplers:
            resamp.set_resamp_ratio(ratio)

    def get_first_decim(self):
        return self.first_decim

    def set_first_decim(self, first_decim):
        # La decimazione è fissata nei filtri xlating alla costruzione: si
        # aggiorna il valore riportato, ma serve un riavvio perché abbia
        # effetto sulla catena.
        self.first_decim = int(first_decim)
        self.set_if_samp_rate(self.samp_rate / self.first_decim)

    def get_ppm_corr(self):
        return self.ppm_corr

    def set_ppm_corr(self, ppm_corr):
        self.ppm_corr = float(ppm_corr)
        if self._source_ctl is not None:
            self._source_ctl.set_freq_corr(self.ppm_corr, 0)

    def get_sdr_gain(self):
        return self.sdr_gain

    def set_sdr_gain(self, gain):
        self.sdr_gain = float(gain)
        if self._source_ctl is not None:
            self._source_ctl.set_gain(self.sdr_gain, 0)

    def get_sdr_ifgain(self):
        return self.sdr_ifgain

    def set_sdr_ifgain(self, gain):
        self.sdr_ifgain = float(gain)
        if self._source_ctl is not None:
            self._source_ctl.set_if_gain(self.sdr_ifgain, 0)

    def get_sdr_bbgain(self):
        return self.sdr_bbgain

    def set_sdr_bbgain(self, gain):
        self.sdr_bbgain = float(gain)
        if self._source_ctl is not None:
            self._source_ctl.set_bb_gain(self.sdr_bbgain, 0)

    def get_options_low_pass(self):
        return self.options_low_pass

    def set_options_low_pass(self, low_pass):
        self.options_low_pass = float(low_pass)
        taps = self._taps()
        for xlate in self._xlating:
            xlate.set_taps(taps)

    def get_out_sample_rate(self):
        return self.out_sample_rate

    def get_first_port(self):
        return self.first_port

    # -- offset per canale -------------------------------------------------

    def _set_offset(self, idx0, value, fine):
        if not 0 <= idx0 < self.channels:
            raise IndexError(f"canale fuori intervallo: {idx0 + 1}")
        if fine:
            self._fine_offsets[idx0] = float(value)
        else:
            self._offsets[idx0] = float(value)
        self._xlating[idx0].set_center_freq(
            self._offsets[idx0] + self._fine_offsets[idx0]
        )

    def get_xlate_offset(self, channel):
        """Offset del canale ``channel`` (1-based), in Hz."""
        return self._offsets[int(channel) - 1]

    def set_xlate_offset(self, channel, value):
        self._set_offset(int(channel) - 1, value, fine=False)

    def get_channel_freq(self, channel):
        """Frequenza assoluta del canale ``channel`` (1-based), in Hz."""
        idx = int(channel) - 1
        return self.freq + self._offsets[idx] + self._fine_offsets[idx]


def _install_channel_accessors():
    """Crea ``get/set_xlate_offsetN`` e ``get/set_xlate_offset_fineN``.

    telive costruisce i nomi dei metodi concatenando l'indice del canale
    (``sprintf(buf2, "xlate_offset%i", i)``), quindi servono metodi distinti
    per ogni canale invece di un unico metodo parametrico.
    """
    def make(idx0, fine):
        def getter(self):
            store = self._fine_offsets if fine else self._offsets
            return store[idx0]

        def setter(self, value):
            self._set_offset(idx0, value, fine)

        return getter, setter

    for idx0 in range(MAX_CHANNELS):
        for fine in (False, True):
            suffix = "_fine" if fine else ""
            name = f"xlate_offset{suffix}{idx0 + 1}"
            getter, setter = make(idx0, fine)
            getter.__name__ = f"get_{name}"
            setter.__name__ = f"set_{name}"
            setattr(OsmoTetraRX, getter.__name__, getter)
            setattr(OsmoTetraRX, setter.__name__, setter)


_install_channel_accessors()


# -- riga di comando -------------------------------------------------------


def eng_float(text):
    """Converte "435M", "12.5k", "2.4e6" in float."""
    text = str(text).strip()
    suffixes = {"k": 1e3, "K": 1e3, "M": 1e6, "m": 1e6, "G": 1e9, "g": 1e9}
    if text and text[-1] in suffixes:
        return float(text[:-1]) * suffixes[text[-1]]
    return float(text)


def build_parser():
    p = argparse.ArgumentParser(
        prog="osmotetra_rx.py",
        description="Ricevitore TETRA multicanale headless per telive.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--channels", type=int, default=1,
                   help=f"numero di canali (1..{MAX_CHANNELS})")
    p.add_argument("--freq", type=eng_float, default=435e6,
                   help="frequenza centrale del ricevitore in Hz (es. 391.1M)")
    p.add_argument("--samp-rate", type=eng_float, default=2e6,
                   help="frequenza di campionamento dell'SDR in Hz")
    p.add_argument("--first-decim", type=int, default=32,
                   help="decimazione del filtro di canale")
    p.add_argument("--out-rate", type=int, default=DEFAULT_OUT_RATE,
                   help="frequenza di uscita per canale (attesa da simdemod3)")
    p.add_argument("--lowpass", type=eng_float, default=12500,
                   help="larghezza del filtro passa-basso di canale in Hz")
    p.add_argument("--gain", type=float, default=38, help="guadagno RF")
    p.add_argument("--if-gain", type=float, default=20, help="guadagno IF")
    p.add_argument("--bb-gain", type=float, default=20, help="guadagno banda base")
    p.add_argument("--ppm", type=float, default=0,
                   help="correzione di frequenza in ppm")
    p.add_argument("--offset", dest="offsets", action="append", type=eng_float,
                   default=None, metavar="HZ",
                   help="offset del canale rispetto alla frequenza centrale, "
                        "ripetibile una volta per canale (es. --offset 500k)")
    p.add_argument("--udp-host", default="127.0.0.1",
                   help="host di destinazione dei campioni IQ")
    p.add_argument("--base-port", type=int, default=42000,
                   help="porta del server XMLRPC; il canale N usa base+N in UDP")
    p.add_argument("--xmlrpc-bind", default="127.0.0.1",
                   help="indirizzo di ascolto del server XMLRPC")
    p.add_argument("--device-args", default="",
                   help="argomenti osmosdr (es. 'rtl=0', 'hackrf=0', 'airspy=0')")
    p.add_argument("--antenna", default="", help="antenna da selezionare")
    p.add_argument("--bandwidth", type=eng_float, default=0,
                   help="larghezza di banda analogica (0 = automatica)")
    p.add_argument("--rx-name", default=None,
                   help="nome del ricevitore mostrato da telive")
    p.add_argument("--source", default="osmosdr", metavar="SPEC",
                   help="'osmosdr', 'file:<percorso.cfile>' oppure 'null' "
                        "(le ultime due per provare la catena senza radio)")
    p.add_argument("--repeat", action="store_true",
                   help="con --source file:, ricomincia da capo alla fine")
    return p


def validate(opts, parser):
    """Controlli che evitano le configurazioni silenziosamente inutili."""
    if not 1 <= opts.channels <= MAX_CHANNELS:
        parser.error(f"--channels deve essere fra 1 e {MAX_CHANNELS}")

    if opts.offsets is None:
        opts.offsets = []
    if len(opts.offsets) > opts.channels:
        parser.error(
            f"forniti {len(opts.offsets)} --offset per {opts.channels} canali"
        )
    # I canali senza offset esplicito restano centrati.
    opts.offsets = list(opts.offsets) + [0.0] * (opts.channels - len(opts.offsets))

    if opts.first_decim < 1:
        parser.error("--first-decim deve essere >= 1")

    # Dopo la decimazione il canale filtrato deve ancora rispettare Nyquist:
    # il passa-basso è a banda singola, quindi la banda occupata è 2*lowpass.
    # (Nota: NON si richiede if_rate >= 2*out_rate. La configurazione
    # standard di telive è 2 Ms/s / 32 = 62,5 ks/s verso 36 ks/s, cioè un
    # rapporto di 1,74: il mmse_resampler è frazionario e la gestisce.)
    if_rate = opts.samp_rate / opts.first_decim
    if if_rate < 2 * opts.lowpass:
        parser.error(
            f"samp_rate/first_decim = {if_rate / 1e3:.1f} kHz non basta per un "
            f"canale largo {2 * opts.lowpass / 1e3:.1f} kHz "
            f"(riduci --first-decim o --lowpass, oppure aumenta --samp-rate)"
        )

    # TETRA usa 18 ksimboli/s e simdemod3 lavora a 2 campioni per simbolo.
    if opts.out_rate < 2 * 18000:
        parser.error(
            f"--out-rate {opts.out_rate} Hz è sotto i 36000 Hz attesi da "
            f"simdemod3_py3.py (2 campioni per simbolo a 18 ksym/s)"
        )

    nyquist = opts.samp_rate / 2
    for i, off in enumerate(opts.offsets, start=1):
        if abs(off) + opts.lowpass > nyquist:
            parser.error(
                f"l'offset del canale {i} ({off / 1e3:.1f} kHz) esce dalla banda "
                f"campionata (±{nyquist / 1e3:.1f} kHz meno il filtro da "
                f"{opts.lowpass / 1e3:.1f} kHz)"
            )

    if opts.base_port + opts.channels > 65535:
        parser.error("--base-port troppo alto per il numero di canali richiesto")

    if opts.rx_name is None:
        plural = "canale" if opts.channels == 1 else "canali"
        opts.rx_name = f"OsmoTetra RX {opts.channels} {plural}"


def main(argv=None):
    parser = build_parser()
    opts = parser.parse_args(argv)
    validate(opts, parser)

    tb = OsmoTetraRX(opts)

    print(
        f"[osmotetra_rx] {opts.rx_name}: {opts.channels} canali, "
        f"centro {opts.freq / 1e6:.4f} MHz, {opts.samp_rate / 1e6:.3f} Ms/s, "
        f"XMLRPC su {opts.xmlrpc_bind}:{opts.base_port}",
        flush=True,
    )
    for i, off in enumerate(opts.offsets, start=1):
        print(
            f"[osmotetra_rx]   canale {i}: offset {off / 1e3:+.1f} kHz "
            f"-> {(opts.freq + off) / 1e6:.4f} MHz, UDP "
            f"{opts.udp_host}:{opts.base_port + i}",
            flush=True,
        )

    stopping = threading.Event()

    def handle_signal(signum, frame):
        if stopping.is_set():
            return
        stopping.set()
        print("[osmotetra_rx] arresto in corso...", flush=True)
        tb.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    tb.start()
    tb.wait()
    return 0


if __name__ == "__main__":
    sys.exit(main())
