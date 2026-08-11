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

    # colonne della tabella chiavi (le "avanzate" si nascondono in modalità guidata)
    COL_TYPE, COL_KEY, COL_MCC, COL_MNC, COL_ADDR, COL_KNUM = range(6)
    ADV_COLS = (COL_MCC, COL_MNC, COL_ADDR, COL_KNUM)

    def _build_ui(self):
        info = QLabel(
            "Compila i campi e premi <b>Salva</b>: l'editor scrive il keyfile che "
            "usa il decoder, senza doverlo modificare a mano.<br>⚠ Funziona <b>solo "
            "con chiavi che possiedi legittimamente</b>. Non rompe alcuna cifratura.")
        info.setWordWrap(True); info.setTextFormat(Qt.RichText)

        # --- Rete ---
        self.mcc = QLineEdit(); self.mcc.setPlaceholderText("es. 222")
        self.mnc = QLineEdit(); self.mnc.setPlaceholderText("es. 55")
        self.mcc.editingFinished.connect(lambda: self.mcc.setText(self._pad(self.mcc.text())))
        self.mnc.editingFinished.connect(lambda: self.mnc.setText(self._pad(self.mnc.text())))
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
        net.addRow("Algoritmo (ksg_type):", self.ksg)
        net.addRow("Classe di sicurezza:", self.sec)
        net.addRow("", self._muted("MCC/MNC vengono completati a 4 cifre (222 → 0222)."))

        # --- Chiavi ---
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Tipo di chiave", "Chiave (80 bit hex)", "MCC", "MNC", "addr", "key_num"])
        self.table.horizontalHeader().setSectionResizeMode(self.COL_KEY, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)

        add_btn = QPushButton("+ Aggiungi chiave"); add_btn.clicked.connect(lambda: self.add_row())
        del_btn = QPushButton("− Rimuovi selezionata"); del_btn.clicked.connect(self.del_row)
        self.show_keys = QCheckBox("Mostra chiavi"); self.show_keys.toggled.connect(self._apply_key_echo)
        self.show_adv = QCheckBox("Parametri avanzati  ▼")
        self.show_adv.setToolTip("Mostra addr, key_num e MCC/MNC specifici per singola chiave")
        self.show_adv.toggled.connect(self._toggle_adv)

        keyhint = self._muted(
            "<b>Tipo di chiave</b>: di solito <b>1</b> (CCK/SCK), oppure <b>16</b> per "
            "una chiave TEA1 accorciata a 32 bit (8 cifre) da riempire con zeri fino a "
            "20 cifre (80 bit). La <b>chiave</b> è esadecimale: 20 cifre = 80 bit.")

        key_box = QGroupBox("Chiavi")
        kb = QVBoxLayout(key_box)
        toolrow = QHBoxLayout()
        toolrow.addWidget(add_btn); toolrow.addWidget(del_btn)
        toolrow.addStretch(1)
        toolrow.addWidget(self.show_keys); toolrow.addWidget(self.show_adv)
        kb.addLayout(toolrow)
        kb.addWidget(self.table)
        kb.addWidget(keyhint)

        # --- pulsanti ---
        gen_btn = QPushButton("🔎  Mostra file generato"); gen_btn.clicked.connect(self.show_generated)
        load_btn = QPushButton("Ricarica dal file"); load_btn.clicked.connect(self.load)
        save_btn = QPushButton("💾  Salva"); save_btn.clicked.connect(self.save)
        close_btn = QPushButton("Chiudi"); close_btn.clicked.connect(self.close)
        btns = QHBoxLayout()
        btns.addWidget(gen_btn); btns.addStretch(1)
        btns.addWidget(load_btn); btns.addWidget(save_btn); btns.addWidget(close_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(info)
        layout.addWidget(net_box)
        layout.addWidget(key_box, 1)
        layout.addWidget(self._muted(f"File: {self.keyfile}"))
        layout.addLayout(btns)
        self.resize(700, 520)
        self._toggle_adv(False)   # parte in modalità guidata

    def add_row(self, mcc="", mnc="", addr="00000000", key_type=1, key_num="0", key=""):
        r = self.table.rowCount()
        self.table.insertRow(r)
        combo = QComboBox()
        for label, val in KEY_TYPES:
            combo.addItem(label, val)
        idx = combo.findData(int(key_type))
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.table.setCellWidget(r, self.COL_TYPE, combo)
        edit = QLineEdit(key)
        edit.setPlaceholderText("20 cifre esadecimali")
        edit.setEchoMode(QLineEdit.Normal if self.show_keys.isChecked() else QLineEdit.Password)
        self.table.setCellWidget(r, self.COL_KEY, edit)
        self.table.setItem(r, self.COL_MCC, QTableWidgetItem(mcc))
        self.table.setItem(r, self.COL_MNC, QTableWidgetItem(mnc))
        self.table.setItem(r, self.COL_ADDR, QTableWidgetItem(addr))
        self.table.setItem(r, self.COL_KNUM, QTableWidgetItem(str(key_num)))

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

    # -- generazione / salvataggio ----------------------------------------

    def _network_line(self):
        mcc, mnc = self._pad(self.mcc.text()), self._pad(self.mnc.text())
        line = (f"network mcc {mcc} mnc {mnc} ksg_type {self.ksg.currentData()} "
                f"security_class {self.sec.currentData()}")
        return mcc, mnc, line

    def _generate(self, validate):
        """Costruisce il testo del keyfile. Se validate, controlla le chiavi e
        restituisce None (dopo aver avvisato) su errore."""
        mcc, mnc, netline = self._network_line()
        if validate and (not mcc or not mnc):
            QMessageBox.warning(self, "Manca la rete", "Inserisci MCC e MNC della rete.")
            return None
        lines = ["# keyfile generato dall'editor di OsmoTetra",
                 "# Decifra SOLO con chiavi in tuo possesso legittimo.", "", netline]
        for r in range(self.table.rowCount()):
            key = self.table.cellWidget(r, self.COL_KEY).text().strip().lower()
            if not key:
                continue
            if validate:
                if any(ch not in "0123456789abcdef" for ch in key):
                    QMessageBox.warning(self, "Chiave non valida",
                                        f"La chiave alla riga {r + 1} deve contenere solo "
                                        f"cifre esadecimali (0-9, a-f).")
                    return None
                if len(key) != 20:
                    res = QMessageBox.question(
                        self, "Controlla la lunghezza",
                        f"Riga {r + 1}: hai inserito {len(key)} cifre esadecimali = "
                        f"{len(key) * 4} bit.\nIl formato standard di questo campo è "
                        f"20 cifre = 80 bit.\n\nLa salvo comunque così com'è?",
                        QMessageBox.Yes | QMessageBox.No)
                    if res != QMessageBox.Yes:
                        return None
            kmcc = self._pad(self._cell(r, self.COL_MCC)) or mcc
            kmnc = self._pad(self._cell(r, self.COL_MNC)) or mnc
            ktype = self.table.cellWidget(r, self.COL_TYPE).currentData()
            lines.append(
                f"key mcc {kmcc} mnc {kmnc} addr {self._cell(r, self.COL_ADDR) or '00000000'} "
                f"key_type {ktype} key_num {self._cell(r, self.COL_KNUM) or '0'} key {key}")
        return "\n".join(lines) + "\n"

    def show_generated(self):
        text = self._generate(validate=False)
        dlg = QDialog(self)
        dlg.setWindowTitle("File generato — anteprima")
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("Questo è ciò che l'editor scriverà nel keyfile:"))
        view = QPlainTextEdit(); view.setReadOnly(True); view.setPlainText(text)
        mono = QFont("Monospace"); mono.setStyleHint(QFont.TypeWriter); view.setFont(mono)
        v.addWidget(view)
        b = QPushButton("Chiudi"); b.clicked.connect(dlg.accept)
        v.addWidget(b)
        dlg.resize(620, 380); dlg.exec_()

    def save(self):
        text = self._generate(validate=True)
        if text is None:
            return
        mcc, mnc, _ = self._network_line()
        nkeys = text.count("\nkey mcc")
        summary = (f"Rete: {mcc} / {mnc}\nAlgoritmo: {self.ksg.currentText()}\n"
                   f"Security class: {self.sec.currentData()}\n"
                   f"Chiavi configurate: {nkeys}\nFile: {self.keyfile}")
        if QMessageBox.question(self, "Confermi il salvataggio?",
                                summary + "\n\nSalvo la configurazione?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            self.keyfile.parent.mkdir(parents=True, exist_ok=True)
            self.keyfile.write_text(text, encoding="utf-8")
            os.chmod(self.keyfile, 0o600)   # materiale crittografico: solo il tuo utente
        except OSError as exc:
            QMessageBox.critical(self, "Errore", f"Impossibile scrivere {self.keyfile}:\n{exc}")
            return
        QMessageBox.information(
            self, "Salvato",
            f"Chiavi salvate in:\n{self.keyfile}\n(permessi riservati al tuo utente, 0600)\n\n"
            f"Avvia (o riavvia) la ricezione per usarle.")

    # -- comportamento GUI -------------------------------------------------

    def _toggle_adv(self, on):
        for c in self.ADV_COLS:
            self.table.setColumnHidden(c, not on)

    def _apply_key_echo(self):
        mode = QLineEdit.Normal if self.show_keys.isChecked() else QLineEdit.Password
        for r in range(self.table.rowCount()):
            w = self.table.cellWidget(r, self.COL_KEY)
            if w is not None:
                w.setEchoMode(mode)

    # -- helper -----------------------------------------------------------
    def _cell(self, r, c):
        it = self.table.item(r, c)
        return it.text().strip() if it else ""

    @staticmethod
    def _pad(s):
        s = str(s).strip()
        return s.zfill(4) if s.isdigit() else s

    @staticmethod
    def _muted(text):
        lbl = QLabel(text); lbl.setWordWrap(True); lbl.setTextFormat(Qt.RichText)
        lbl.setStyleSheet("color: palette(mid);")
        return lbl

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

        # sorgente SDR "amichevole": locale (USB) oppure remota (rete / VM)
        self.sdr_kind = QComboBox()
        self.sdr_kind.addItem("Chiavetta locale (USB)", "local")
        self.sdr_kind.addItem("Chiavetta remota (rete / VM)", "remote")
        self.sdr_kind.currentIndexChanged.connect(self._apply_mode)
        self.remote_ip = QLineEdit("192.168.64.1")
        self.remote_port = QSpinBox()
        self.remote_port.setRange(1, 65535); self.remote_port.setValue(1234)
        self.remote_w = QWidget()
        rr = QHBoxLayout(self.remote_w); rr.setContentsMargins(0, 0, 0, 0)
        rr.addWidget(QLabel("IP")); rr.addWidget(self.remote_ip, 1)
        rr.addWidget(QLabel("porta")); rr.addWidget(self.remote_port)

        # campo tecnico (solo modalità Avanzata): stringa gr-osmosdr manuale
        self.device = QComboBox()
        self.device.setEditable(True)
        for label, args in DEVICE_PRESETS:
            self.device.addItem(label, args)
        self.device.currentIndexChanged.connect(
            lambda i: self.device.setEditText(self.device.itemData(i) or ""))
        self.device.setEditText("")
        self.device.lineEdit().setPlaceholderText("vuoto = usa la selezione qui sopra")

        self.show_spectrum = QCheckBox("Mostra la finestra dello spettro (grafici + controlli)")
        self.show_spectrum.setChecked(True)

        # interruttore Base / Avanzata
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Base", "Avanzata"])
        self.mode_combo.currentIndexChanged.connect(self._apply_mode)
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Modalità:")); mode_row.addWidget(self.mode_combo)
        mode_row.addStretch(1)

        form_box = QGroupBox("Sintonia")
        self.form = QFormLayout(form_box)
        form = self.form
        form.addRow("Frequenza del canale:", self.freq)
        form.addRow("Guadagno RF:", self.gain)
        form.addRow("Sorgente SDR:", self.sdr_kind)
        form.addRow("Indirizzo remoto:", self.remote_w)
        form.addRow("Correzione (ppm):", self.ppm)
        form.addRow("Dispositivo (manuale):", self.device)
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
        layout.addLayout(mode_row)
        layout.addWidget(form_box)
        layout.addLayout(btn_row)
        layout.addWidget(self.status)
        layout.addWidget(log_box, 1)
        self.resize(560, 580)
        self._apply_mode()   # imposta la visibilità Base/Avanzata iniziale

    # -- modalità Base / Avanzata -----------------------------------------

    def _apply_mode(self, *_):
        advanced = self.mode_combo.currentText() == "Avanzata"
        remote = self.sdr_kind.currentData() == "remote"
        self._row_visible(self.remote_w, remote)
        self._row_visible(self.ppm, advanced)
        self._row_visible(self.device, advanced)

    def _row_visible(self, field, visible):
        field.setVisible(visible)
        lbl = self.form.labelForField(field)
        if lbl is not None:
            lbl.setVisible(visible)

    def _device_args(self):
        """Costruisce la stringa gr-osmosdr dalla scelta dell'utente."""
        if self.mode_combo.currentText() == "Avanzata":
            manual = self.device.currentText().strip()
            if manual:
                return manual
        if self.sdr_kind.currentData() == "remote":
            return f"rtl_tcp={self.remote_ip.text().strip()}:{self.remote_port.value()}"
        return ""

    def _set_running(self, running: bool):
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        for w in (self.freq, self.gain, self.ppm, self.device, self.show_spectrum,
                  self.sdr_kind, self.remote_ip, self.remote_port, self.mode_combo):
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
        device_args = self._device_args()

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
