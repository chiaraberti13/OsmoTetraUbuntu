#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OsmoTetra — lanciatore grafico minimo.

Una finestrella: imposti frequenza, guadagno e dispositivo, premi «Avvia» e
parte da sola l'intera catena provata di SQ5BPF:

    flowgraph headless (osmotetra_rx.py)  →  UDP 42001
        →  receiver1udp (socat | simdemod3_telive.py | tetra-rx)  →  UDP 7379
            →  telive  (finestra ncurses, l'interfaccia vera e propria)

Il flowgraph e receiver1udp girano in sottofondo (il loro output finisce nel
riquadro dei log); telive si apre in un terminale, perché è lì che guardi il
traffico. Alla chiusura si ferma tutto.

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox,
    QVBoxLayout, QWidget,
)

# --------------------------------------------------------------------------
# Percorsi: dove l'installer ha messo i sorgenti compilati.
# --------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
HOME = Path(os.environ.get("OSMOTETRA_HOME", str(Path.home() / "telive2")))
OSMO_SRC = HOME / "osmo-tetra-sq5bpf-2" / "src"
TELIVE_DIR = HOME / "telive-2"
FLOWGRAPH = HERE / "osmotetra_rx.py"
#: interprete con i binding GNU Radio (apt installa tutto per python3 di sistema).
GR_PYTHON = os.environ.get("OSMOTETRA_PYTHON", "python3")
XMLRPC_PORT = 42000
TELIVE_UDP_PORT = 7379

#: Dispositivi noti a gr-osmosdr; (etichetta, stringa device-args).
DEVICE_PRESETS = [
    ("Chiavetta USB (rilevamento automatico)", ""),
    ("Chiavetta USB — prima (rtl=0)", "rtl=0"),
    ("Chiavetta USB — seconda (rtl=1)", "rtl=1"),
    ("Chiavetta via rete (rtl_tcp=127.0.0.1:1234)", "rtl_tcp=127.0.0.1:1234"),
    ("HackRF", "hackrf=0"),
    ("Airspy", "airspy=0"),
]

# telive vuole un terminale grande (203×60): dove possibile lo apriamo massimizzato.
TERMINALS = [
    ("gnome-terminal", ["gnome-terminal", "--maximize", "--title=telive — OsmoTetra", "--"]),
    ("xfce4-terminal", ["xfce4-terminal", "--maximize", "--title=telive", "-x"]),
    ("mate-terminal", ["mate-terminal", "--maximize", "--title=telive", "-x"]),
    ("konsole", ["konsole", "-p", "tabtitle=telive", "-e"]),
    ("x-terminal-emulator", ["x-terminal-emulator", "-T", "telive — OsmoTetra", "-e"]),
    ("xterm", ["xterm", "-geometry", "203x60", "-T", "telive", "-e"]),
]


class Emitter(QObject):
    """Ponte thread-safe: i thread di lettura mandano righe alla GUI."""
    line = pyqtSignal(str)


class Launcher(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OsmoTetra — ricevitore TETRA")
        self._procs: list[subprocess.Popen] = []
        self._telive_proc: subprocess.Popen | None = None
        self._telive_seen = False
        self._emitter = Emitter()
        self._emitter.line.connect(self._append_log)
        self._build_ui()
        self._set_running(False)

    # -- interfaccia ------------------------------------------------------

    def _build_ui(self):
        title = QLabel("OsmoTetra")
        f = QFont(); f.setPointSize(16); f.setBold(True); title.setFont(f)
        subtitle = QLabel("Imposta i parametri e premi «Avvia»: si apre telive.")
        subtitle.setStyleSheet("color: palette(mid);")

        self.freq = QDoubleSpinBox()
        self.freq.setRange(100.0, 1000.0)
        self.freq.setDecimals(4)
        self.freq.setSingleStep(0.0125)
        self.freq.setValue(390.5)
        self.freq.setSuffix(" MHz")

        self.gain = QSpinBox()
        self.gain.setRange(0, 50)
        self.gain.setValue(38)
        self.gain.setSuffix(" dB")

        self.ppm = QDoubleSpinBox()
        self.ppm.setRange(-100.0, 100.0)
        self.ppm.setDecimals(1)
        self.ppm.setValue(0.0)
        self.ppm.setSuffix(" ppm")

        self.device = QComboBox()
        self.device.setEditable(True)
        for label, args in DEVICE_PRESETS:
            self.device.addItem(label, args)
        self.device.currentIndexChanged.connect(
            lambda i: self.device.setEditText(self.device.itemData(i) or ""))
        self.device.setEditText("")
        self.device.lineEdit().setPlaceholderText("vuoto = prima chiavetta trovata")

        self.show_spectrum = QCheckBox("Mostra la finestra dello spettro (grafici + controlli)")
        self.show_spectrum.setChecked(True)

        form_box = QGroupBox("Sintonia")
        form = QFormLayout(form_box)
        form.addRow("Frequenza del canale:", self.freq)
        form.addRow("Guadagno RF:", self.gain)
        form.addRow("Correzione:", self.ppm)
        form.addRow("Dispositivo:", self.device)
        form.addRow("", self.show_spectrum)

        self.start_btn = QPushButton("▶  Avvia")
        self.start_btn.clicked.connect(self.on_start)
        self.stop_btn = QPushButton("■  Ferma")
        self.stop_btn.clicked.connect(self.on_stop)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn)

        self.status = QLabel("Fermo")
        self.status.setAlignment(Qt.AlignCenter)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        mono = QFont("Monospace"); mono.setStyleHint(QFont.TypeWriter); mono.setPointSize(9)
        self.log.setFont(mono)
        log_box = QGroupBox("Log (flowgraph e ricevitore)")
        log_layout = QVBoxLayout(log_box)
        log_layout.addWidget(self.log)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(form_box)
        layout.addLayout(btn_row)
        layout.addWidget(self.status)
        layout.addWidget(log_box, 1)
        self.resize(560, 560)

    def _set_running(self, running: bool):
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        for w in (self.freq, self.gain, self.ppm, self.device, self.show_spectrum):
            w.setEnabled(not running)
        if running:
            self.status.setText("In esecuzione — guarda la finestra di telive")
            self.status.setStyleSheet("color: white; background:#2e9e5b; padding:6px; border-radius:4px;")
        else:
            self.status.setText("Fermo")
            self.status.setStyleSheet("color: white; background:#9aa0a6; padding:6px; border-radius:4px;")

    def _append_log(self, text: str):
        self.log.appendPlainText(text.rstrip("\n"))

    def _log(self, text: str):
        self._emitter.line.emit(text)

    # -- avvio della catena ----------------------------------------------

    def on_start(self):
        problem = self._preflight()
        if problem:
            QMessageBox.critical(self, "Manca qualcosa", problem)
            return

        self.log.clear()
        self.status.setText("Avvio in corso…")
        self.status.setStyleSheet("color: white; background:#e8a33d; padding:6px; border-radius:4px;")
        QApplication.processEvents()

        freq_hz = self.freq.value() * 1e6
        device_args = self.device.currentText().strip()

        # 1) flowgraph headless
        fg_cmd = [
            GR_PYTHON, str(FLOWGRAPH),
            "--freq", f"{freq_hz:.0f}",
            "--gain", str(self.gain.value()),
            "--ppm", str(self.ppm.value()),
            "--device-args", device_args,
        ]
        if self.show_spectrum.isChecked():
            fg_cmd.append("--gui")
        self._log(f"$ {' '.join(fg_cmd)}")
        try:
            fg = subprocess.Popen(
                fg_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, start_new_session=True)
        except OSError as exc:
            QMessageBox.critical(self, "Errore", f"Impossibile avviare il flowgraph:\n{exc}")
            self._set_running(False)
            return
        self._procs.append(fg)
        self._pump(fg, "rx")

        # 2) aspetta l'SDR: XMLRPC pronto, oppure il flowgraph è morto (niente radio)
        if not self._wait_for_receiver(fg, timeout=20):
            self._log("[launcher] il ricevitore SDR non è partito: catena fermata.")
            self.on_stop()
            QMessageBox.critical(
                self, "Ricevitore non partito",
                "Il flowgraph si è chiuso all'avvio (di solito manca la radio, "
                "il driver DVB-T è ancora caricato, oppure rtl_tcp non risponde).\n\n"
                "Guarda le righe [rx] nel log qui sotto: dicono cosa manca e cosa fare.")
            return

        # 3) receiver1udp (socat | simdemod3_telive.py | tetra-rx) in sottofondo
        self._log(f"$ ./receiver1udp 1   (in {OSMO_SRC})")
        try:
            rx = subprocess.Popen(
                ["./receiver1udp", "1"], cwd=str(OSMO_SRC),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, start_new_session=True)
        except OSError as exc:
            self.on_stop()
            QMessageBox.critical(self, "Errore", f"Impossibile avviare receiver1udp:\n{exc}")
            return
        self._procs.append(rx)
        self._pump(rx, "demod")

        # 4) telive in un terminale
        if not self._launch_telive(freq_hz):
            self.on_stop()
            return

        self._set_running(True)
        self._log("[launcher] catena avviata. telive è nella sua finestra "
                  "(ingrandiscila se serve: telive vuole 203×60).")
        # sorveglia flowgraph/ricevitore (morte improvvisa) e telive (chiuso).
        self._telive_seen = False
        self._watch_timer = QTimer(self)
        self._watch_timer.timeout.connect(self._check_alive)
        self._watch_timer.start(1000)

    def _preflight(self) -> str | None:
        if not FLOWGRAPH.is_file():
            return f"Flowgraph non trovato: {FLOWGRAPH}"
        if not (OSMO_SRC / "receiver1udp").is_file() or not (OSMO_SRC / "tetra-rx").is_file():
            return (f"Ricevitore osmo non trovato in {OSMO_SRC}.\n"
                    f"Esegui prima l'installazione:  ./install.sh")
        if not (TELIVE_DIR / "telive").is_file():
            return (f"telive non trovato in {TELIVE_DIR}.\n"
                    f"Esegui prima l'installazione:  ./install.sh")
        if self._port_open(XMLRPC_PORT):
            return (f"La porta {XMLRPC_PORT} è già occupata: un'altra istanza è "
                    f"forse in esecuzione. Premi «Ferma» o chiudila prima.")
        return None

    def _wait_for_receiver(self, fg: subprocess.Popen, timeout: int) -> bool:
        """True quando l'XMLRPC del flowgraph risponde; False se il flowgraph muore."""
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            if fg.poll() is not None:
                return False  # morto: niente radio
            if self._port_open(XMLRPC_PORT):
                return True
            time.sleep(0.25)
        return self._port_open(XMLRPC_PORT)

    def _launch_telive(self, freq_hz: float) -> bool:
        term = self._find_terminal()
        if term is None:
            QMessageBox.critical(
                self, "Terminale non trovato",
                "Non trovo un emulatore di terminale (gnome-terminal, xterm…).\n"
                f"Apri un terminale ed esegui a mano:\n  cd {TELIVE_DIR} && ./telive")
            return False

        # Le variabili d'ambiente vengono scritte DENTRO il comando (export …):
        # gnome-terminal riusa un server con il proprio ambiente, quindi un env
        # passato solo a Popen non arriverebbe a telive. Così è a prova di quirk.
        telive_env = {
            "PATH": os.environ.get("PATH", "") + ":/tetra/bin",
            "TETRA_OUTDIR": "/tetra/in",
            "TETRA_LOGFILE": "/tetra/log/telive.log",
            "TETRA_PORT": str(TELIVE_UDP_PORT),
            "TETRA_GR_XMLRPC_URL": f"http://127.0.0.1:{XMLRPC_PORT}/",
            # non lasciare che telive sposti da solo il ricevitore già sintonizzato
            "TETRA_RX_BASEBAND_AUTOCORRECT": "0",
            "TETRA_AUTO_TUNE": "0",
        }
        exports = "; ".join(f"export {k}={sh_quote(v)}" for k, v in telive_env.items())
        inner = (f"{exports}; cd {sh_quote(str(TELIVE_DIR))} && ./telive; "
                 f"echo; echo '[telive terminato — premi Invio]'; read")
        cmd = term + ["bash", "-c", inner]
        self._log(f"[launcher] apro telive con: {term[0]}")
        try:
            self._telive_proc = subprocess.Popen(cmd, start_new_session=True)
        except OSError as exc:
            QMessageBox.critical(self, "Errore", f"Impossibile aprire il terminale di telive:\n{exc}")
            return False
        return True

    # -- arresto ----------------------------------------------------------

    def on_stop(self):
        if hasattr(self, "_watch_timer"):
            self._watch_timer.stop()
        self._telive_seen = False
        for proc in (self._telive_proc, *reversed(self._procs)):
            _terminate(proc)
        # gnome-terminal apre telive in un processo server: il nostro handle è
        # già uscito, quindi chiudiamo telive per nome (best-effort).
        subprocess.run(["pkill", "-x", "telive"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._telive_proc = None
        self._procs.clear()
        self._set_running(False)
        self._log("[launcher] fermato.")

    def _check_alive(self):
        # 1) uno stadio di sottofondo è morto (es. chiavetta staccata a metà)?
        names = ("flowgraph", "ricevitore")
        for proc, name in zip(self._procs, names):
            if proc.poll() is not None:
                self._log(f"[launcher] lo stadio «{name}» si è fermato: chiudo la catena.")
                self.on_stop()
                return
        # 2) telive chiuso dall'utente? (rilevato per nome: regge ogni terminale)
        if self._telive_running():
            self._telive_seen = True
        elif self._telive_seen:
            self._log("[launcher] telive è stato chiuso: fermo la catena.")
            self.on_stop()

    @staticmethod
    def _telive_running() -> bool:
        return subprocess.run(
            ["pgrep", "-x", "telive"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0

    def closeEvent(self, event):
        self.on_stop()
        event.accept()

    # -- utilità ----------------------------------------------------------

    def _pump(self, proc: subprocess.Popen, tag: str):
        """Legge stdout del processo in un thread e lo manda al log della GUI."""
        def run():
            assert proc.stdout is not None
            for raw in proc.stdout:
                self._log(f"[{tag}] {raw.rstrip()}")
        threading.Thread(target=run, daemon=True).start()

    @staticmethod
    def _port_open(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            return s.connect_ex(("127.0.0.1", port)) == 0

    @staticmethod
    def _find_terminal():
        for name, argv in TERMINALS:
            if shutil.which(name):
                return argv
        return None


def sh_quote(text: str) -> str:
    import shlex
    return shlex.quote(text)


def _terminate(proc):
    if proc is None or proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        try:
            proc.terminate()
        except Exception:
            pass
    try:
        proc.wait(timeout=5)
    except Exception:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            pass


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("OsmoTetra")
    win = Launcher()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
