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
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog,
    QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
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
#: il keyfile che tetra-rx usa (-k sample_keyfile), nella dir dei sorgenti osmo.
KEYFILE = OSMO_SRC / "sample_keyfile"

#: tipi di cifratura TETRA (ksg_type) e classi di sicurezza.
KSG_TYPES = [("TEA1", 1), ("TEA2", 2), ("TEA3", 3), ("TEA4", 4),
             ("TEA5", 5), ("TEA6", 6), ("TEA7", 7)]
SECURITY_CLASSES = [("2 — SCK", 2), ("3 — CCK+DCK", 3)]
#: tipi di chiave (key_type) col loro significato.
KEY_TYPES = [("1 — CCK/SCK", 1), ("2 — DCK", 2), ("4 — MGCK", 4),
             ("8 — GCK", 8), ("16 — TEA1 32-bit (riempi a 80)", 16)]

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


class KeyEditor(QDialog):
    """Editor grafico del keyfile di decifratura: compili i campi e lui scrive
    il file che usa il decoder, senza doverlo modificare a mano."""

    def __init__(self, keyfile: Path = KEYFILE, parent=None):
        super().__init__(parent)
        self.keyfile = Path(keyfile)
        self.setWindowTitle("OsmoTetra — chiavi di decifratura")
        self._build_ui()
        self.load()

    def _build_ui(self):
        info = QLabel(
            "Compila i campi e premi <b>Salva</b>: scrive il keyfile che usa il "
            "decoder, senza doverlo modificare a mano.<br>⚠ Funziona <b>solo con "
            "chiavi che possiedi legittimamente</b>. Non rompe alcuna cifratura.")
        info.setWordWrap(True)
        info.setTextFormat(Qt.RichText)

        self.mcc = QLineEdit(); self.mcc.setPlaceholderText("es. 0222")
        self.mnc = QLineEdit(); self.mnc.setPlaceholderText("es. 0055")
        self.ksg = QComboBox()
        for label, val in KSG_TYPES:
            self.ksg.addItem(label, val)
        self.sec = QComboBox()
        for label, val in SECURITY_CLASSES:
            self.sec.addItem(label, val)
        net_box = QGroupBox("Rete")
        net = QFormLayout(net_box)
        net.addRow("MCC:", self.mcc)
        net.addRow("MNC:", self.mnc)
        net.addRow("Cifratura (ksg_type):", self.ksg)
        net.addRow("Classe di sicurezza:", self.sec)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["MCC", "MNC", "addr", "Tipo chiave", "key_num", "Chiave (80 bit, esadecimale)"])
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        add_btn = QPushButton("+ Aggiungi chiave"); add_btn.clicked.connect(lambda: self.add_row())
        del_btn = QPushButton("− Rimuovi selezionata"); del_btn.clicked.connect(self.del_row)
        keyhint = QLabel(
            "Tipo chiave <b>16</b> = chiave TEA1 accorciata a 32 bit (8 cifre) da "
            "riempire con zeri fino a 80 bit (20 cifre). Le altre = chiave intera a "
            "80 bit (20 cifre esadecimali). MCC/MNC vuoti = quelli della rete.")
        keyhint.setWordWrap(True); keyhint.setTextFormat(Qt.RichText)
        keyhint.setStyleSheet("color: palette(mid);")
        key_box = QGroupBox("Chiavi")
        kb = QVBoxLayout(key_box)
        kb.addWidget(self.table)
        row = QHBoxLayout(); row.addWidget(add_btn); row.addWidget(del_btn); row.addStretch(1)
        kb.addLayout(row)
        kb.addWidget(keyhint)

        load_btn = QPushButton("Ricarica dal file"); load_btn.clicked.connect(self.load)
        save_btn = QPushButton("💾  Salva"); save_btn.clicked.connect(self.save)
        close_btn = QPushButton("Chiudi"); close_btn.clicked.connect(self.close)
        btns = QHBoxLayout()
        btns.addWidget(QLabel(f"File: {self.keyfile}"))
        btns.addStretch(1)
        btns.addWidget(load_btn); btns.addWidget(save_btn); btns.addWidget(close_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(info)
        layout.addWidget(net_box)
        layout.addWidget(key_box, 1)
        layout.addLayout(btns)
        self.resize(680, 500)

    def add_row(self, mcc="", mnc="", addr="00000000", key_type=1, key_num="0", key=""):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(mcc or self.mcc.text().strip()))
        self.table.setItem(r, 1, QTableWidgetItem(mnc or self.mnc.text().strip()))
        self.table.setItem(r, 2, QTableWidgetItem(addr))
        combo = QComboBox()
        for label, val in KEY_TYPES:
            combo.addItem(label, val)
        idx = combo.findData(int(key_type))
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.table.setCellWidget(r, 3, combo)
        self.table.setItem(r, 4, QTableWidgetItem(str(key_num)))
        self.table.setItem(r, 5, QTableWidgetItem(key))

    def del_row(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    def load(self):
        self.table.setRowCount(0)
        net, keys = self._parse(self.keyfile)
        self.mcc.setText(net.get("mcc", ""))
        self.mnc.setText(net.get("mnc", ""))
        self._select(self.ksg, int(net.get("ksg_type", 1) or 1))
        self._select(self.sec, int(net.get("security_class", 2) or 2))
        for k in keys:
            self.add_row(k.get("mcc", ""), k.get("mnc", ""), k.get("addr", "00000000"),
                         int(k.get("key_type", 1) or 1), k.get("key_num", "0"), k.get("key", ""))
        if not keys:
            self.add_row()

    def save(self):
        mcc = self.mcc.text().strip(); mnc = self.mnc.text().strip()
        if not mcc or not mnc:
            QMessageBox.warning(self, "Manca la rete", "Inserisci MCC e MNC della rete.")
            return
        lines = [
            "# keyfile generato dall'editor di OsmoTetra",
            "# Decifra SOLO con chiavi in tuo possesso legittimo.",
            "",
            f"network mcc {mcc} mnc {mnc} ksg_type {self.ksg.currentData()} "
            f"security_class {self.sec.currentData()}",
        ]
        for r in range(self.table.rowCount()):
            key = self._cell(r, 5).lower()
            if not key:
                continue
            if any(ch not in "0123456789abcdef" for ch in key):
                QMessageBox.warning(self, "Chiave non valida",
                                    f"La chiave alla riga {r + 1} deve essere esadecimale.")
                return
            if len(key) != 20:
                res = QMessageBox.question(
                    self, "Lunghezza chiave",
                    f"La chiave alla riga {r + 1} ha {len(key)} cifre invece di 20 "
                    f"(80 bit). La salvo lo stesso?", QMessageBox.Yes | QMessageBox.No)
                if res != QMessageBox.Yes:
                    return
            combo = self.table.cellWidget(r, 3)
            lines.append(
                f"key mcc {self._cell(r, 0) or mcc} mnc {self._cell(r, 1) or mnc} "
                f"addr {self._cell(r, 2) or '00000000'} key_type {combo.currentData()} "
                f"key_num {self._cell(r, 4) or '0'} key {key}")
        try:
            self.keyfile.parent.mkdir(parents=True, exist_ok=True)
            self.keyfile.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Errore", f"Impossibile scrivere {self.keyfile}:\n{exc}")
            return
        QMessageBox.information(
            self, "Salvato",
            f"Chiavi salvate in:\n{self.keyfile}\n\nAvvia (o riavvia) la ricezione per usarle.")

    # -- helper -----------------------------------------------------------
    def _cell(self, r, c):
        it = self.table.item(r, c)
        return it.text().strip() if it else ""

    @staticmethod
    def _select(combo, value):
        idx = combo.findData(value)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    @staticmethod
    def _tokens(line):
        parts = line.split()
        return {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}

    def _parse(self, path):
        net, keys = {}, []
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return net, keys
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("network ") and not net:
                net = self._tokens(line)
            elif line.startswith("key "):
                keys.append(self._tokens(line))
        return net, keys


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
        self.keys_btn = QPushButton("🔑  Chiavi di decifratura…")
        self.keys_btn.clicked.connect(self.open_keys)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addWidget(self.keys_btn)

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

    def open_keys(self):
        KeyEditor(KEYFILE, self).exec_()

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
    # 'osmotetra chiavi' apre solo l'editor delle chiavi.
    if "--keys" in sys.argv[1:]:
        dlg = KeyEditor(KEYFILE)
        dlg.show()
        sys.exit(app.exec_())
    win = Launcher()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
