"""Rilevamento delle dipendenze di OsmoTetraUbuntu.

Oltre ai controlli ovvi (binari compilati, comandi presenti), qui si risolve
un problema reale: **quale interprete Python sa importare GNU Radio**.

I binding di GNU Radio sono compilati per la versione di Python del
pacchetto Ubuntu (3.12 su 24.04). Se sulla macchina è installato un altro
Python che occupa ``/usr/bin/python3`` o viene prima nel PATH — cosa comune
su macchine di sviluppo, con pyenv, conda o build da sorgente — allora sia il
flowgraph sia ``simdemod3_py3.py`` (che ha ``#!/usr/bin/env python3`` come
shebang) partono con l'interprete sbagliato e falliscono con
``ModuleNotFoundError: No module named 'gnuradio.gr.gr_python'``.
Per questo entrambi vengono invocati con l'interprete rilevato qui, invece
di affidarsi allo shebang.

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from . import paths

#: Interpreti candidati, in ordine di preferenza.
_PYTHON_CANDIDATES = (
    "/usr/bin/python3",       # su una Ubuntu 24.04 stock è già quello giusto
    "python3",
    "/usr/bin/python3.13",
    "/usr/bin/python3.12",
    "python3.13",
    "python3.12",
)

_PROBE = "from gnuradio import gr; print(gr.version())"

_gnuradio_python_cache: tuple[str | None, str] | None = None


def find_gnuradio_python(force: bool = False) -> tuple[str | None, str]:
    """Trova un interprete capace di importare GNU Radio.

    Restituisce ``(percorso, versione_gnuradio)``; ``(None, "")`` se nessun
    candidato funziona. Il risultato è memorizzato: sondare più interpreti
    costa qualche centinaio di millisecondi.

    ``OSMOTETRA_PYTHON`` ha la precedenza su tutto, per i casi che questa
    euristica non copre.
    """
    global _gnuradio_python_cache
    if _gnuradio_python_cache is not None and not force:
        return _gnuradio_python_cache

    candidates: list[str] = []
    override = os.environ.get("OSMOTETRA_PYTHON")
    if override:
        candidates.append(override)
    candidates.extend(_PYTHON_CANDIDATES)
    # L'interprete che sta eseguendo la GUI è un candidato come gli altri,
    # ma non necessariamente il migliore: la GUI usa PyQt5, non GNU Radio.
    candidates.append(sys.executable)

    seen: set[str] = set()
    for candidate in candidates:
        resolved = shutil.which(candidate) if not candidate.startswith("/") else candidate
        if not resolved or resolved in seen or not Path(resolved).exists():
            continue
        seen.add(resolved)
        try:
            out = subprocess.run(
                [resolved, "-c", _PROBE],
                capture_output=True, text=True, timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if out.returncode == 0:
            version = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
            _gnuradio_python_cache = (resolved, version)
            return _gnuradio_python_cache

    _gnuradio_python_cache = (None, "")
    return _gnuradio_python_cache


def has_osmosdr(python: str | None = None) -> bool:
    """Verifica che il modulo osmosdr sia importabile dall'interprete dato."""
    python = python or find_gnuradio_python()[0]
    if not python:
        return False
    try:
        out = subprocess.run(
            [python, "-c", "import osmosdr"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return out.returncode == 0


def find_terminal() -> tuple[str | None, list[str]]:
    """Trova un emulatore di terminale capace di aprire una finestra 203x60.

    Restituisce ``(comando, argomenti_geometria)``. La lista è vuota per i
    terminali che non accettano una geometria in caratteri.
    """
    for name in ("xterm", "gnome-terminal", "konsole", "xfce4-terminal",
                 "mate-terminal", "lxterminal"):
        path = shutil.which(name)
        if path:
            return path, []
    return None, []


@dataclass
class Check:
    """Esito di un singolo controllo."""

    name: str
    ok: bool
    detail: str
    #: True se la mancanza impedisce del tutto di avviare la catena.
    required: bool = True
    hint: str = ""

    @property
    def symbol(self) -> str:
        if self.ok:
            return "ok"
        return "errore" if self.required else "assente"


def _check_binary(name: str, path: Path, hint: str, required: bool = True) -> Check:
    if path.is_file() and os.access(path, os.X_OK):
        return Check(name, True, str(path), required)
    return Check(name, False, f"non trovato: {path}", required, hint)


def _check_command(name: str, command: str, hint: str, required: bool = True) -> Check:
    found = shutil.which(command)
    if found:
        return Check(name, True, found, required)
    return Check(name, False, f"comando '{command}' non nel PATH", required, hint)


def run_checks() -> list[Check]:
    """Esegue tutti i controlli, dal più fondamentale al più accessorio."""
    checks: list[Check] = []
    apt = "sudo apt-get install"

    python, gr_version = find_gnuradio_python()
    if python:
        checks.append(Check(
            "GNU Radio", True,
            f"{gr_version} (interprete: {python})",
        ))
    else:
        checks.append(Check(
            "GNU Radio", False,
            "nessun interprete Python riesce a importare gnuradio",
            hint=f"{apt} gnuradio  —  se GNU Radio è installato ma il problema "
                 f"persiste, indica l'interprete giusto con OSMOTETRA_PYTHON",
        ))

    if python:
        ok = has_osmosdr(python)
        checks.append(Check(
            "gr-osmosdr", ok,
            "modulo osmosdr importabile" if ok else "modulo osmosdr non importabile",
            hint=f"{apt} gr-osmosdr",
        ))
    else:
        checks.append(Check("gr-osmosdr", False, "non verificabile senza GNU Radio",
                            hint=f"{apt} gr-osmosdr"))

    checks.append(_check_command("socat", "socat",
                                 f"{apt} socat"))

    checks.append(_check_binary(
        "tetra-rx", paths.tetra_rx(),
        "esegui ./install.sh per compilare osmo-tetra-sq5bpf-2"))

    checks.append(Check(
        "simdemod3", paths.simdemod().is_file(),
        str(paths.simdemod()) if paths.simdemod().is_file()
        else f"non trovato: {paths.simdemod()}",
        hint="esegui ./install.sh per clonare osmo-tetra-sq5bpf-2",
    ))

    checks.append(_check_binary(
        "telive", paths.telive_bin(),
        "esegui ./install.sh per compilare telive"))

    checks.append(Check(
        "flowgraph", paths.flowgraph().is_file(),
        str(paths.flowgraph()) if paths.flowgraph().is_file()
        else f"non trovato: {paths.flowgraph()}",
        hint="reinstalla l'applicazione con ./install.sh",
    ))

    terminal, _ = find_terminal()
    checks.append(Check(
        "terminale", terminal is not None,
        terminal or "nessun emulatore di terminale trovato",
        hint=f"{apt} xterm  (telive richiede una finestra da 203x60 caratteri)",
    ))

    # Da qui in poi: nulla di bloccante.
    codec_bins = ["cdecoder", "sdecoder"]
    codec_ok = all((paths.tetra_bin() / b).is_file() for b in codec_bins)
    checks.append(Check(
        "codec vocale ACELP", codec_ok,
        str(paths.tetra_bin()) if codec_ok
        else "non installato: nessun audio, il resto funziona",
        required=False,
        hint="./install.sh --with-codec  (scarica il codec dal sito ETSI)",
    ))

    checks.append(_check_command(
        "aplay", "aplay", f"{apt} alsa-utils", required=False))
    checks.append(_check_command(
        "sox", "sox", f"{apt} sox", required=False))
    checks.append(_check_command(
        "oggenc", "oggenc", f"{apt} vorbis-tools", required=False))

    try:
        import PyQt5  # noqa: F401
        checks.append(Check("PyQt5", True, "disponibile", required=False))
    except ImportError:
        checks.append(Check(
            "PyQt5", False, "non disponibile: solo interfaccia a riga di comando",
            required=False, hint=f"{apt} python3-pyqt5",
        ))

    return checks


def blocking_failures(checks: list[Check] | None = None) -> list[Check]:
    """Controlli falliti che impediscono l'avvio della catena."""
    checks = checks if checks is not None else run_checks()
    return [c for c in checks if c.required and not c.ok]
