"""Traduzione della configurazione nelle variabili d'ambiente di telive.

telive non ha file di configurazione né opzioni da riga di comando: si
configura interamente con variabili ``TETRA_*``, che upstream vengono
impostate a mano nello script ``rxx``. Qui le generiamo dalla ``Config``.

Riferimenti: ``telive.c`` (righe 2729-2905, lettura delle variabili) e i
commenti nello script ``rxx`` del repository telive.

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import shlex

from . import paths
from .config import Config


def build_env(cfg: Config) -> dict[str, str]:
    """Variabili ``TETRA_*`` corrispondenti alla configurazione."""
    tetra = paths.tetra_dir()
    tc = cfg.telive

    env: dict[str, str] = {
        # Dove telive scrive le chiamate registrate in ACELP grezzo.
        "TETRA_OUTDIR": str(tetra / "in"),
        "TETRA_LOGFILE": str(tetra / "log" / "telive.log"),
        "TETRA_PORT": str(tc.udp_port),
        "TETRA_FREQLOGFILE": str(tetra / "log" / "telive_frequency.log"),
        "TETRA_FREQUENCY_REPORT_FILE": str(tetra / "log" / "telive_frequency_report.txt"),
    }

    if tc.keys:
        env["TETRA_KEYS"] = tc.keys
    if tc.ssi_filter:
        env["TETRA_SSI_FILTER"] = tc.ssi_filter
    if tc.ssi_descriptions:
        env["TETRA_SSI_DESCRIPTIONS"] = tc.ssi_descriptions

    if tc.kml_enabled:
        env["TETRA_KML_FILE"] = str(tetra / "log" / "tetra.kml")
        env["TETRA_KML_INTERVAL"] = str(max(1, tc.kml_interval))

    # Controllo del ricevitore via XMLRPC: senza questa variabile telive
    # disabilita sintonia, scansione e correzione automatica del PPM.
    if tc.xmlrpc_enabled:
        env["TETRA_GR_XMLRPC_URL"] = f"http://127.0.0.1:{cfg.base_port}/"
        env["TETRA_RX_GAIN"] = str(int(cfg.sdr.gain))
        env["TETRA_RX_PPM"] = str(cfg.sdr.ppm)
        env["TETRA_RX_PPM_AUTOCORRECT"] = "1" if tc.ppm_autocorrect else "0"
        env["TETRA_RX_BASEBAND_AUTOCORRECT"] = "1" if tc.baseband_autocorrect else "0"
        env["TETRA_RX_BASEBAND"] = f"{cfg.sdr.freq_hz / 1e6:.6f}"
        env["TETRA_AUTO_TUNE"] = "1" if tc.auto_tune else "0"
        if tc.scan_list:
            env["TETRA_SCAN_LIST"] = tc.scan_list

        # Frequenze iniziali dei canali, in MHz, separate da ';' e con ';'
        # anche in fondo (telive analizza l'elenco fino al separatore finale).
        tune = "".join(
            f"{cfg.channel_freq_hz(idx) / 1e6:.6f};"
            for idx, _ in cfg.active_channels
        )
        if tune:
            env["TETRA_RX_TUNE"] = tune

    # I timeout a 0 restano ai default interni di telive.
    for name, value in (
        ("TETRA_REC_TIMEOUT", tc.rec_timeout),
        ("TETRA_SSI_TIMEOUT", tc.ssi_timeout),
        ("TETRA_IDX_TIMEOUT", tc.idx_timeout),
        ("TETRA_CURPLAYING_TIMEOUT", tc.curplaying_timeout),
        ("TETRA_FREQ_TIMEOUT", tc.freq_timeout),
    ):
        if value:
            env[name] = str(int(value))

    return env


def build_runner_script(cfg: Config) -> str:
    """Genera lo script che apre telive dentro il terminale.

    Serve un file eseguibile perché gli emulatori di terminale accettano un
    solo comando: mettere ``env A=1 B=2 ...`` sulla riga di comando funziona
    con xterm ma non con gnome-terminal, e diventa illeggibile.

    La directory di lavoro deve essere quella dei sorgenti di telive: il
    programma cerca ``tetra.xml`` (codici MCC/MNC) e ``ssi_descriptions`` nel
    percorso corrente.
    """
    env = build_env(cfg)
    lines = [
        "#!/bin/bash",
        "# Generato da OsmoTetraUbuntu a ogni avvio: le modifiche vanno perse.",
        "",
        "ulimit -c unlimited",
        "",
        # tplay e i binari del codec devono essere raggiungibili: telive
        # riproduce l'audio con popen("tplay").
        f"export PATH={shlex.quote(str(paths.tetra_bin()))}:$PATH",
        "",
    ]
    for key in sorted(env):
        lines.append(f"export {key}={shlex.quote(env[key])}")

    lines += [
        "",
        f"cd {shlex.quote(str(paths.telive_src()))} || exit 1",
        "",
        "./telive",
        "status=$?",
        "",
        "# Se telive termina da solo (errore di avvio, terminale troppo",
        "# piccolo) la finestra si chiuderebbe prima che il messaggio sia",
        "# leggibile: qui si ferma in attesa di un tasto.",
        'if [ "$status" -ne 0 ]; then',
        '    echo',
        '    echo "telive è terminato con codice $status."',
        '    echo "Premi Invio per chiudere questa finestra."',
        '    read -r _',
        "fi",
        "exit $status",
    ]
    return "\n".join(lines) + "\n"


def write_runner_script(cfg: Config):
    """Scrive lo script di avvio di telive e restituisce il percorso."""
    path = paths.tetra_bin() / "telive-run"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_runner_script(cfg), encoding="utf-8")
    path.chmod(0o755)
    return path
