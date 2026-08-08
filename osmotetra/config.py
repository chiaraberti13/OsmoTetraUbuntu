"""Configurazione di OsmoTetraUbuntu.

Un unico oggetto ``Config`` raccoglie tutto ciò che l'utente può impostare:
i parametri dell'SDR, i canali, le opzioni di telive e quelle di registrazione.
Viene serializzato in JSON in ``~/.config/osmotetra/config.json`` e può essere
salvato come profilo con nome.

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from . import paths

MAX_CHANNELS = 6
#: Frequenza di uscita per canale attesa da simdemod3_py3.py.
OUT_RATE = 36000


@dataclass
class Channel:
    """Un canale di ricezione: un ramo del flowgraph più il suo decoder."""

    #: Scostamento dalla frequenza centrale dell'SDR, in Hz.
    offset_hz: float = 0.0
    enabled: bool = True

    # Opzioni di tetra-rx (vedi tetra-rx.c: show_help)
    afc: bool = False            # -a  pseudo-AFC (richiede l'ingresso float)
    reassemble: bool = True      # -r  ricomposizione dei PDU frammentati
    sds_as_text: bool = True     # -s  mostra come testo gli SDS sconosciuti
    allow_encrypted: bool = False  # -e  prova a interpretare i pacchetti cifrati

    def tetra_rx_flags(self) -> list[str]:
        """Argomenti da passare a tetra-rx per questo canale.

        Nota: ``-a`` funziona solo insieme a ``-i`` (ingresso float). Nella
        catena con simdemod3 l'ingresso è già a bit, quindi ``-a`` non viene
        emesso: la correzione di frequenza la fa simdemod3, che manda a telive
        i messaggi AFCVAL.
        """
        flags: list[str] = []
        if self.reassemble:
            flags.append("-r")
        if self.sds_as_text:
            flags.append("-s")
        if self.allow_encrypted:
            flags.append("-e")
        return flags


@dataclass
class SdrConfig:
    """Parametri del ricevitore radio."""

    device_args: str = ""          # es. "rtl=0", "hackrf=0", "airspy=0"
    freq_hz: float = 391_100_000.0  # frequenza centrale
    samp_rate: float = 2_000_000.0
    first_decim: int = 32
    lowpass_hz: float = 12_500.0
    gain: float = 38.0
    if_gain: float = 20.0
    bb_gain: float = 20.0
    ppm: float = 0.0
    antenna: str = ""
    bandwidth_hz: float = 0.0
    #: 'osmosdr', 'file:<percorso>' oppure 'null'. Le ultime due servono a
    #: provare la catena senza radio collegata.
    source: str = "osmosdr"
    repeat_file: bool = True

    @property
    def if_samp_rate(self) -> float:
        return self.samp_rate / self.first_decim if self.first_decim else 0.0


@dataclass
class TeliveConfig:
    """Impostazioni di telive, che a runtime diventano variabili TETRA_*."""

    udp_port: int = 7379
    #: Tasti "premuti" all'avvio (TETRA_KEYS). 'm' = mutessi.
    keys: str = "m"
    ssi_filter: str = ""
    ssi_descriptions: str = ""
    kml_enabled: bool = True
    kml_interval: int = 3
    xmlrpc_enabled: bool = True
    auto_tune: bool = False
    ppm_autocorrect: bool = True
    baseband_autocorrect: bool = True
    scan_list: str = "390-395/12.5;420-430/12.5"
    # Timeout interni (vedi commenti nello script rxx di telive). 0 = default.
    rec_timeout: int = 0
    ssi_timeout: int = 0
    idx_timeout: int = 0
    curplaying_timeout: int = 0
    freq_timeout: int = 0


@dataclass
class RecordingConfig:
    """Registrazione e ricompressione audio."""

    #: Avvia tetrad, che ricomprime le chiamate ACELP in OGG.
    tetrad_enabled: bool = False


@dataclass
class TerminalConfig:
    """Come aprire il terminale che ospita telive.

    telive è un'interfaccia ncurses che pretende 203x60 caratteri: sotto
    quella dimensione lo schermo risulta illeggibile.
    """

    #: Comando del terminale; vuoto = rilevamento automatico.
    command: str = ""
    columns: int = 203
    rows: int = 60
    font: str = "Monospace"
    font_size: int = 10


@dataclass
class Config:
    """Configurazione completa dell'applicazione."""

    sdr: SdrConfig = field(default_factory=SdrConfig)
    telive: TeliveConfig = field(default_factory=TeliveConfig)
    recording: RecordingConfig = field(default_factory=RecordingConfig)
    terminal: TerminalConfig = field(default_factory=TerminalConfig)
    channels: list[Channel] = field(default_factory=lambda: [Channel()])
    #: Porta del server XMLRPC del flowgraph; il canale N usa base+N in UDP.
    base_port: int = 42000
    udp_host: str = "127.0.0.1"

    # -- canali attivi ----------------------------------------------------

    @property
    def active_channels(self) -> list[tuple[int, Channel]]:
        """Canali abilitati, con l'indice 1-based usato da telive come RXID.

        L'indice resta quello della posizione in ``channels``: disabilitare
        il canale 2 non rinumera il 3, altrimenti cambierebbero porte UDP e
        RXID dei canali rimasti.
        """
        return [(i, ch) for i, ch in enumerate(self.channels, start=1) if ch.enabled]

    def channel_udp_port(self, index1: int) -> int:
        """Porta UDP su cui il flowgraph pubblica il canale ``index1``."""
        return self.base_port + index1

    def channel_freq_hz(self, index1: int) -> float:
        return self.sdr.freq_hz + self.channels[index1 - 1].offset_hz

    def set_channel_count(self, count: int) -> None:
        """Porta l'elenco dei canali a ``count`` conservando quelli esistenti."""
        count = max(1, min(int(count), MAX_CHANNELS))
        while len(self.channels) < count:
            self.channels.append(Channel())
        del self.channels[count:]

    # -- validazione ------------------------------------------------------

    def validate(self) -> list[str]:
        """Restituisce l'elenco dei problemi bloccanti (vuoto se va tutto bene).

        Serve a intercettare le configurazioni che "partono" ma non producono
        nulla, che sono il modo più comune di perdere tempo con telive.
        """
        errors: list[str] = []
        sdr = self.sdr

        if sdr.samp_rate <= 0:
            errors.append("La frequenza di campionamento deve essere positiva.")
        if sdr.first_decim < 1:
            errors.append("La decimazione deve essere almeno 1.")
        if sdr.lowpass_hz <= 0:
            errors.append("Il filtro passa-basso deve essere positivo.")

        if sdr.samp_rate > 0 and sdr.first_decim >= 1 and sdr.lowpass_hz > 0:
            if sdr.if_samp_rate < 2 * sdr.lowpass_hz:
                errors.append(
                    f"Dopo la decimazione restano {sdr.if_samp_rate / 1e3:.1f} kHz, "
                    f"insufficienti per un canale largo "
                    f"{2 * sdr.lowpass_hz / 1e3:.1f} kHz: riduci la decimazione "
                    f"o il filtro, oppure aumenta il campionamento."
                )

            nyquist = sdr.samp_rate / 2
            for idx, ch in self.active_channels:
                if abs(ch.offset_hz) + sdr.lowpass_hz > nyquist:
                    errors.append(
                        f"Canale {idx}: l'offset di {ch.offset_hz / 1e3:+.1f} kHz "
                        f"esce dalla banda campionata "
                        f"(±{nyquist / 1e3:.1f} kHz meno il filtro)."
                    )

        if not self.active_channels:
            errors.append("Nessun canale abilitato.")

        if not 1 <= self.base_port <= 65535 - MAX_CHANNELS:
            errors.append(f"Porta base fuori intervallo: {self.base_port}.")
        if not 1 <= self.telive.udp_port <= 65535:
            errors.append(f"Porta di telive fuori intervallo: {self.telive.udp_port}.")

        # Il flowgraph usa base_port per XMLRPC e base_port+N per i canali:
        # una sovrapposizione con la porta di telive fa sparire i dati.
        used = {self.base_port} | {
            self.channel_udp_port(i) for i, _ in self.active_channels
        }
        if self.telive.udp_port in used:
            errors.append(
                f"La porta di telive ({self.telive.udp_port}) è già usata dal "
                f"ricevitore: scegline un'altra o sposta la porta base."
            )

        if self.sdr.source.startswith("file:"):
            path = self.sdr.source[len("file:"):]
            if not path:
                errors.append("Sorgente 'file:' senza percorso.")
            elif not Path(path).expanduser().is_file():
                errors.append(f"File IQ non trovato: {path}")
        elif self.sdr.source not in ("osmosdr", "null"):
            errors.append(f"Sorgente non riconosciuta: {self.sdr.source}")

        return errors

    def warnings(self) -> list[str]:
        """Segnalazioni non bloccanti."""
        out: list[str] = []
        sdr = self.sdr
        # Le RTL-SDR perdono campioni sopra i 2,4 Ms/s su molti host USB.
        if "rtl" in sdr.device_args.lower() or not sdr.device_args:
            if sdr.samp_rate > 2_400_000:
                out.append(
                    f"{sdr.samp_rate / 1e6:.2f} Ms/s è oltre il limite affidabile "
                    f"delle chiavette RTL-SDR (2,4 Ms/s): possibili campioni persi."
                )
        if sdr.source != "osmosdr":
            out.append(
                f"Sorgente '{sdr.source}': modalità di prova senza radio."
            )
        if self.telive.auto_tune and len(self.active_channels) == 1:
            out.append(
                "La sintonia automatica ha senso con più canali: con uno solo "
                "telive non ha ricevitori liberi da sintonizzare."
            )
        return out

    # -- serializzazione --------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        """Ricostruisce una Config da un dizionario.

        Le chiavi sconosciute vengono ignorate e quelle mancanti mantengono
        il default, così una configurazione scritta da un'altra versione
        dell'applicazione resta caricabile.
        """
        cfg = cls()
        data = data or {}

        for name, klass in _NESTED.items():
            sub = data.get(name)
            if isinstance(sub, dict):
                valid = {f.name for f in fields(klass)}
                setattr(cfg, name,
                        klass(**{k: v for k, v in sub.items() if k in valid}))

        chans = data.get("channels")
        if isinstance(chans, list):
            valid = {f.name for f in fields(Channel)}
            parsed = [
                Channel(**{k: v for k, v in c.items() if k in valid})
                for c in chans[:MAX_CHANNELS] if isinstance(c, dict)
            ]
            if parsed:
                cfg.channels = parsed

        for key in ("base_port", "udp_host"):
            if key in data:
                setattr(cfg, key, data[key])
        return cfg

    def save(self, path: Path | None = None) -> Path:
        path = path or paths.config_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        # Scrittura atomica: un'interruzione non deve lasciare un JSON monco.
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        tmp.replace(path)
        return path

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or paths.config_file()
        if not path.is_file():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Una config illeggibile non deve impedire l'avvio: si riparte
            # dai default e l'utente può risalvare.
            return cls()
        return cls.from_dict(data)


#: Sotto-oggetti di Config, usati da ``Config.from_dict`` per ricostruirli.
_NESTED = {
    "sdr": SdrConfig,
    "telive": TeliveConfig,
    "recording": RecordingConfig,
    "terminal": TerminalConfig,
}


# -- profili ---------------------------------------------------------------

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._ -]")


def profile_path(name: str) -> Path:
    """Percorso del profilo ``name``, con il nome reso sicuro per il filesystem."""
    safe = _SAFE_NAME.sub("_", name.strip()) or "profilo"
    return paths.profiles_dir() / f"{safe}.json"


def list_profiles() -> list[str]:
    directory = paths.profiles_dir()
    if not directory.is_dir():
        return []
    return sorted(p.stem for p in directory.glob("*.json"))


def save_profile(cfg: Config, name: str) -> Path:
    path = profile_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    return cfg.save(path)


def load_profile(name: str) -> Config:
    return Config.load(profile_path(name))


def delete_profile(name: str) -> bool:
    path = profile_path(name)
    if path.is_file():
        path.unlink()
        return True
    return False
