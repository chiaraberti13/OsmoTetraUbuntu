"""Percorsi usati da OsmoTetraUbuntu.

Tutto vive nella home dell'utente: i sorgenti upstream e i dati sotto
``$OSMOTETRA_PREFIX`` (default ``~/.local/share/osmotetra``), la
configurazione sotto ``~/.config/osmotetra``.

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "osmotetra"


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else default


def prefix() -> Path:
    """Directory di installazione (sorgenti upstream, dati, binari)."""
    return _env_path("OSMOTETRA_PREFIX", Path.home() / ".local" / "share" / APP_NAME)


def config_dir() -> Path:
    base = _env_path("XDG_CONFIG_HOME", Path.home() / ".config")
    return base / APP_NAME


def config_file() -> Path:
    return config_dir() / "config.json"


def profiles_dir() -> Path:
    return config_dir() / "profiles"


def src_dir() -> Path:
    return prefix() / "src"


def osmo_tetra_src() -> Path:
    """Directory ``src`` di osmo-tetra-sq5bpf-2: contiene tetra-rx e demod/."""
    return src_dir() / "osmo-tetra-sq5bpf-2" / "src"


def telive_src() -> Path:
    """Directory di telive-2: contiene il binario, tetra.xml, ssi_descriptions."""
    return src_dir() / "telive-2"


def tetra_dir() -> Path:
    """Radice dei dati di telive (in/out/log/tmp/bin)."""
    return prefix() / "tetra"


def tetra_bin() -> Path:
    """Directory di tplay, tetrad e dei binari del codec ACELP."""
    return tetra_dir() / "bin"


def log_dir() -> Path:
    return tetra_dir() / "log"


def flowgraph() -> Path:
    """Percorso di osmotetra_rx.py.

    Cerca prima accanto al pacchetto installato (``$PREFIX/lib/gnuradio``),
    poi nella copia di lavoro del repository, così l'app funziona anche
    eseguita direttamente dai sorgenti senza installazione.
    """
    candidates = [
        prefix() / "lib" / "gnuradio" / "osmotetra_rx.py",
        Path(__file__).resolve().parent.parent / "gnuradio" / "osmotetra_rx.py",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def scripts_dir() -> Path:
    """Directory degli script di installazione."""
    candidates = [
        prefix() / "lib" / "scripts",
        Path(__file__).resolve().parent.parent / "scripts",
    ]
    for path in candidates:
        if path.is_dir():
            return path
    return candidates[0]


def simdemod() -> Path:
    """Demodulatore π/4-DQPSK di osmo-tetra-sq5bpf-2 (rinominato in v2)."""
    return osmo_tetra_src() / "demod" / "simdemod3_telive.py"


def sample_keyfile() -> Path:
    """Keyfile di esempio di osmo-tetra-sq5bpf-2: modello per la decrittazione.

    Sta accanto a tetra-rx (nella dir ``src`` del decoder), non in telive-2.
    """
    return osmo_tetra_src() / "sample_keyfile"


def tetra_rx() -> Path:
    return osmo_tetra_src() / "tetra-rx"


def telive_bin() -> Path:
    return telive_src() / "telive"


def ensure_runtime_dirs() -> None:
    """Crea le directory scrivibili a runtime, se mancanti."""
    for path in (config_dir(), profiles_dir(), log_dir(),
                 tetra_dir() / "in", tetra_dir() / "out", tetra_dir() / "tmp"):
        path.mkdir(parents=True, exist_ok=True)
