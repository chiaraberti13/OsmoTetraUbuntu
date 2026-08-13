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

import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog,
    QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QHeaderView, QInputDialog, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem,
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
#: il keyfile che tetra-rx usa (-k sample_keyfile), nella dir dei sorgenti osmo.
KEYFILE = OSMO_SRC / "sample_keyfile"

#: tipi di cifratura TETRA (ksg_type) e classi di sicurezza.
KSG_TYPES = [("TEA1", 1), ("TEA2", 2), ("TEA3", 3), ("TEA4", 4),
             ("TEA5", 5), ("TEA6", 6), ("TEA7", 7)]
SECURITY_CLASSES = [("2 — SCK", 2), ("3 — CCK+DCK", 3)]
#: tipi di chiave (key_type) col loro significato.
KEY_TYPES = [("1 — CCK/SCK", 1), ("2 — DCK", 2), ("4 — MGCK", 4),
             ("8 — GCK", 8), ("16 — TEA1 32-bit (riempi a 80)", 16)]

#: porta su cui il tap riceve dal decoder, prima di inoltrare a telive (7379).
TAP_PORT = 7380

#: dove teniamo i profili di configurazione (non contengono mai chiavi).
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "osmotetra"
PROFILES_FILE = CONFIG_DIR / "profili.json"

#: qualunque sequenza esadecimale lunga è materiale di chiave: fuori dai file
#: di diagnostica. tetra-rx stampa le chiavi caricate all'avvio, quindi finiscono
#: nel log: la diagnostica va ripulita prima di uscire da questo computer.
_HEX_RUN = re.compile(r"\b[0-9a-fA-F]{16,}\b")


def redact_keys(text: str) -> str:
    """Sostituisce il materiale di chiave con un segnaposto."""
    return _HEX_RUN.sub("<chiave rimossa>", text)


def _lead_int(tail, base):
    """strtol "leggero": legge il numero iniziale di ``tail`` nella base data."""
    digits = "0123456789abcdefABCDEF" if base == 16 else "0123456789"
    j = 0
    while j < len(tail) and tail[j] in digits:
        j += 1
    if j == 0:
        return None
    try:
        return int(tail[:j], base)
    except ValueError:
        return None


def _field(text, ident, base=None):
    """Come getptr/getptrint di telive: trova ``ident`` e legge cosa segue."""
    i = text.find(ident)
    if i < 0:
        return None
    tail = text[i + len(ident):]
    if base is None:
        return tail.split(None, 1)[0] if tail.split() else ""
    return _lead_int(tail, base)


def _kf_tokens(line):
    """«network mcc 0222 mnc 0055 …» → {'mcc': '0222', 'mnc': '0055', …}"""
    parts = line.split()
    return {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def parse_keyfile(path):
    """Legge il keyfile e restituisce (riga «network», elenco righe «key»).
    Un file mancante o illeggibile non è un errore: si torna vuoti."""
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
            net = _kf_tokens(line)
        elif line.startswith("key "):
            keys.append(_kf_tokens(line))
    return net, keys


class StatusTap(QObject):
    """Si mette fra il decoder e telive: riceve i messaggi TETMON su TAP_PORT,
    li **inoltra tali e quali** a telive (7379) e ne estrae lo stato (MCC/MNC,
    sincronizzazione, cifratura). Se qualcosa nella lettura va storto, i byte
    inoltrati restano identici: la decodifica di telive non si può rompere."""

    TELIVE_PORT = TELIVE_UDP_PORT

    def __init__(self):
        super().__init__()
        self._sock = None
        self._out = None
        self._thread = None
        self._running = False
        self._lock = threading.Lock()
        self._st = self._empty()

    @staticmethod
    def _empty():
        return {"signal_ts": 0.0, "sync_ts": 0.0, "mcc": None, "mnc": None,
                "ccode": None, "la": None, "control": None, "crypt": 0,
                "enc_ts": 0.0}

    def start(self) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", TAP_PORT))
            s.settimeout(0.5)
        except OSError:
            return False
        self._sock = s
        self._out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        with self._lock:
            self._st = self._empty()
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._running = False
        for s in (self._sock, self._out):
            try:
                s.close()
            except Exception:
                pass
        self._sock = self._out = None

    def snapshot(self):
        with self._lock:
            return dict(self._st)

    def _run(self):
        while self._running:
            try:
                data, _ = self._sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            # 1) inoltra SUBITO a telive, byte per byte (mai deve fallire prima)
            try:
                self._out.sendto(data, ("127.0.0.1", self.TELIVE_PORT))
            except OSError:
                pass
            # 2) poi, in modo difensivo, estrai lo stato
            try:
                self._parse(data.decode("latin1"))
            except Exception:
                pass

    def _parse(self, text):
        func = _field(text, "FUNC:")
        if not func:
            return
        now = time.time()
        with self._lock:
            if func.startswith(("AFCVAL", "BURST")):
                self._st["signal_ts"] = now
            elif func.startswith("NETINFO"):
                self._st["sync_ts"] = now
                self._st["signal_ts"] = now
                self._st["mcc"] = _field(text, "MCC:", 16)
                self._st["mnc"] = _field(text, "MNC:", 16)
                self._st["ccode"] = _field(text, "CCODE:", 16)
                self._st["la"] = _field(text, "LA:", 10)
                dlf = _field(text, "DLF:", 10)
                self._st["control"] = dlf / 1e6 if dlf else None
                crypt = _field(text, "CRYPT:", 10) or 0
                self._st["crypt"] = crypt
                if crypt >= 2:
                    self._st["enc_ts"] = now
            elif func.startswith(("GET_KSG_KEY", "ENCINFO", "CRYPTO_GET_KEY")):
                self._st["enc_ts"] = now

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

    def __init__(self, keyfile: Path = KEYFILE, parent=None, detected=None):
        super().__init__(parent)
        self.keyfile = Path(keyfile)
        #: (mcc, mnc) letti dall'aria mentre la ricezione girava, se disponibili.
        self.detected = detected
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

        # «Usa rete rilevata»: compila MCC/MNC con quelli letti dall'aria.
        self.use_detected = QPushButton()
        self.use_detected.clicked.connect(self._fill_detected)
        if self.detected and self.detected[0] is not None:
            d_mcc, d_mnc = self.detected
            self.use_detected.setText(f"↧  Usa rete rilevata  (MCC {d_mcc} / MNC {d_mnc})")
            self.use_detected.setToolTip(
                "Copia qui MCC e MNC letti dal segnale, completati a 4 cifre.")
        else:
            self.use_detected.setText("↧  Usa rete rilevata")
            self.use_detected.setEnabled(False)
            self.use_detected.setToolTip(
                "Disponibile dopo che la ricezione ha agganciato una rete: "
                "avvia OsmoTetra, attendi «Rete rilevata» nel pannello Stato, "
                "poi riapri questa finestra.")
        net.addRow("", self.use_detected)
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

    def _fill_detected(self):
        if not self.detected or self.detected[0] is None:
            return
        d_mcc, d_mnc = self.detected
        self.mcc.setText(self._pad(str(d_mcc)))
        self.mnc.setText(self._pad(str(d_mnc)))

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
    def _parse(path):
        return parse_keyfile(path)


class Launcher(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OsmoTetra — ricevitore TETRA")
        self._procs: list[subprocess.Popen] = []
        self._telive_proc: subprocess.Popen | None = None
        self._telive_seen = False
        self.tap: StatusTap | None = None
        self._log_lines: list[tuple[bool, str]] = []   # (importante, testo)
        self._emitter = Emitter()
        self._emitter.line.connect(self._append_log)
        self._build_ui()
        self._set_running(False)
        # il pannello Stato si aggiorna sempre, anche a catena ferma
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_status)
        self._status_timer.start(1000)

    # -- interfaccia ------------------------------------------------------

    def _build_ui(self):
        title = QLabel("OsmoTetra")
        f = QFont(); f.setPointSize(16); f.setBold(True); title.setFont(f)
        subtitle = QLabel("Imposta i parametri e premi «Avvia»: si apre telive.")
        subtitle.setStyleSheet("color: palette(mid);")

        self.freq = QDoubleSpinBox()
        self.freq.setRange(100.0, 1000.0)
        self.freq.setDecimals(4)
        # i canali TETRA stanno su un reticolo di 25 kHz: la freccetta si muove
        # di un canale per volta, così non si finisce a metà strada fra due.
        self.freq.setSingleStep(0.025)
        self.freq.setValue(390.5)
        self.freq.setSuffix(" MHz")
        self.freq.valueChanged.connect(self._check_raster)
        self.freq_hint = QLabel("")
        self.freq_hint.setWordWrap(True)

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
        form.addRow("", self.freq_hint)
        form.addRow("Guadagno RF:", self.gain)
        form.addRow("Sorgente SDR:", self.sdr_kind)
        form.addRow("Indirizzo remoto:", self.remote_w)
        form.addRow("", self.show_spectrum)
        self.tune_box = form_box

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

        # --- schede -------------------------------------------------------
        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_reception(), "Ricezione")
        self.tabs.addTab(self._tab_status(), "Stato")
        self.tabs.addTab(self._tab_network(), "Rete")
        self.tabs.addTab(self._tab_keys(), "Chiavi")
        self.tabs.addTab(self._tab_log(), "Log")
        self.adv_tab_index = self.tabs.addTab(self._tab_advanced(), "Avanzate")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(mode_row)
        layout.addLayout(btn_row)
        layout.addWidget(self.status)
        layout.addWidget(self.tabs, 1)
        self.resize(640, 720)
        self._load_profiles()
        self._apply_mode()   # imposta la visibilità Base/Avanzata iniziale
        self._refresh_status()

    # -- le schede ---------------------------------------------------------

    def _tab_reception(self):
        """Ricezione: quello che serve per partire, e i profili."""
        w = QWidget(); v = QVBoxLayout(w)
        v.addWidget(self.tune_box)

        self.profile_combo = QComboBox()
        self.profile_combo.setToolTip(
            "Un profilo ricorda frequenza, guadagno, sorgente SDR e le altre "
            "impostazioni di questa scheda. Non contiene mai chiavi.")
        self.profile_combo.activated.connect(self._apply_profile)
        save_prof = QPushButton("Salva come…"); save_prof.clicked.connect(self._save_profile)
        del_prof = QPushButton("Elimina"); del_prof.clicked.connect(self._delete_profile)
        pbox = QGroupBox("Profili")
        ph = QHBoxLayout(pbox)
        ph.addWidget(self.profile_combo, 1); ph.addWidget(save_prof); ph.addWidget(del_prof)
        v.addWidget(pbox)
        v.addWidget(self._muted(
            "Suggerimento: salva un profilo per ogni rete che ascolti, così "
            "ritrovi i valori giusti con un clic."))
        v.addStretch(1)
        return w

    def _tab_status(self):
        w = QWidget(); v = QVBoxLayout(w)
        v.addWidget(self._build_status_box())
        v.addWidget(self._muted(
            "Passa il mouse su una riga per la spiegazione. <b>✓</b> a posto, "
            "<b>!</b> c'è qualcosa da sistemare, <b>·</b> non ancora noto."))
        v.addStretch(1)
        return w

    #: campi del riquadro Rete: (chiave, etichetta, spiegazione del «?»)
    NET_FIELDS = [
        ("mcc", "MCC (Paese)",
         "Mobile Country Code: identifica il Paese della rete. 222 = Italia. "
         "Nel keyfile va scritto a 4 cifre (222 → 0222)."),
        ("mnc", "MNC (rete)",
         "Mobile Network Code: identifica la singola rete dentro il Paese. "
         "Anche questo va a 4 cifre nel keyfile."),
        ("ccode", "Codice colore (CC)",
         "Colour Code: distingue celle vicine che usano la stessa frequenza. "
         "Se cambia mentre ascolti, ti sei spostato su un'altra cella."),
        ("la", "Area di localizzazione (LA)",
         "Location Area: il gruppo di celle in cui i terminali sono registrati."),
        ("control", "Frequenza di discesa",
         "La frequenza del canale di controllo in discesa (dalla rete ai "
         "terminali): è quella che stai ascoltando."),
        ("crypt", "Cifratura",
         "Via etere TETRA segnala SE il traffico è cifrato, non QUALE algoritmo. "
         "L'algoritmo lo scegli tu nella scheda Chiavi."),
        ("seen", "Ultimo aggiornamento",
         "Quando è arrivato l'ultimo messaggio di rete."),
    ]

    def _tab_network(self):
        """Rete: i dati della cella, spiegati uno per uno."""
        w = QWidget(); v = QVBoxLayout(w)
        box = QGroupBox("Rete TETRA rilevata")
        grid = QFormLayout(box)
        self._net_fields = {}
        for key, label, tip in self.NET_FIELDS:
            value = QLabel("—")
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            name = QWidget()
            h = QHBoxLayout(name); h.setContentsMargins(0, 0, 0, 0)
            h.addWidget(QLabel(f"{label}:"))
            help_lbl = QLabel("<b>?</b>")
            help_lbl.setStyleSheet("color: palette(mid);")
            help_lbl.setToolTip(tip)
            h.addWidget(help_lbl); h.addStretch(1)
            grid.addRow(name, value)
            self._net_fields[key] = value
        v.addWidget(box)

        copy_btn = QPushButton("📋  Copia dettagli rete")
        copy_btn.setToolTip("Copia i dati qui sopra negli appunti, come testo.")
        copy_btn.clicked.connect(self._copy_network)
        row = QHBoxLayout(); row.addWidget(copy_btn); row.addStretch(1)
        v.addLayout(row)
        v.addWidget(self._muted(
            "I dati arrivano dai messaggi di rete della cella e compaiono solo "
            "quando la ricezione è agganciata."))
        v.addStretch(1)
        return w

    def _tab_keys(self):
        """Chiavi: stato del keyfile e accesso all'editor."""
        w = QWidget(); v = QVBoxLayout(w)
        box = QGroupBox("Chiavi di decifratura")
        b = QVBoxLayout(box)
        self.keys_summary = QLabel("—")
        self.keys_summary.setWordWrap(True)
        b.addWidget(self.keys_summary)
        open_btn = QPushButton("🔑  Apri l'editor delle chiavi…")
        open_btn.clicked.connect(self.open_keys)
        b.addWidget(open_btn)
        b.addWidget(self._muted(f"File: {KEYFILE}"))
        v.addWidget(box)
        v.addWidget(self._muted(
            "⚠ La decifratura funziona <b>solo con chiavi che possiedi "
            "legittimamente</b> e non rompe alcuna cifratura. Via etere TETRA "
            "segnala <b>se</b> il traffico è cifrato, non <b>quale</b> algoritmo "
            "usa: l'algoritmo (TEA1…TEA7) lo scegli tu, in base a quello che sai "
            "della tua rete. Senza le chiavi giuste le chiamate cifrate restano "
            "mute — è normale."))
        v.addStretch(1)
        return w

    def _tab_log(self):
        w = QWidget(); v = QVBoxLayout(w)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        mono = QFont("Monospace"); mono.setStyleHint(QFont.TypeWriter); mono.setPointSize(9)
        self.log.setFont(mono)
        self.log_tech = QCheckBox("Log tecnico (mostra tutto)")
        self.log_tech.setToolTip(
            "Spento: solo i messaggi che servono a te.\n"
            "Acceso: anche l'output grezzo di flowgraph e ricevitore, "
            "utile da allegare quando chiedi aiuto.")
        self.log_tech.toggled.connect(self._rerender_log)
        diag_btn = QPushButton("💾  Esporta diagnostica…")
        diag_btn.setToolTip("Salva un file di testo con versioni, impostazioni, "
                            "stato e log — senza alcuna chiave.")
        diag_btn.clicked.connect(self._export_diagnostics)
        row = QHBoxLayout()
        row.addWidget(self.log_tech); row.addStretch(1); row.addWidget(diag_btn)
        v.addLayout(row)
        v.addWidget(self.log, 1)
        return w

    def _tab_advanced(self):
        """Avanzate: i parametri tecnici e dove sono le cose."""
        w = QWidget(); v = QVBoxLayout(w)
        box = QGroupBox("Parametri tecnici")
        self.adv_form = QFormLayout(box)
        self.adv_form.addRow("Correzione (ppm):", self.ppm)
        self.adv_form.addRow("Dispositivo (manuale):", self.device)
        self.adv_form.addRow("", self._muted(
            "Il campo «Dispositivo» accetta una stringa gr-osmosdr "
            "(<code>rtl=0</code>, <code>hackrf=0</code>, "
            "<code>rtl_tcp=IP:porta</code>). Se lo lasci vuoto vale la scelta "
            "fatta in «Sorgente SDR»."))
        v.addWidget(box)

        paths = QGroupBox("Dove sono le cose")
        pf = QFormLayout(paths)
        for label, value in (
                ("Sorgenti e binari:", str(HOME)),
                ("Decoder (osmo-tetra):", str(OSMO_SRC)),
                ("Monitor (telive):", str(TELIVE_DIR)),
                ("Keyfile:", str(KEYFILE)),
                ("Interprete GNU Radio:", GR_PYTHON),
                ("Porte:", f"XMLRPC {XMLRPC_PORT} · telive {TELIVE_UDP_PORT} "
                           f"· diagnostica {TAP_PORT}")):
            val = QLabel(value)
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            val.setStyleSheet("color: palette(mid);")
            pf.addRow(label, val)
        v.addWidget(paths)
        v.addStretch(1)
        return w

    @staticmethod
    def _muted(text):
        lbl = QLabel(text); lbl.setWordWrap(True); lbl.setTextFormat(Qt.RichText)
        lbl.setStyleSheet("color: palette(mid);")
        return lbl

    # -- pannello Stato ----------------------------------------------------

    #: righe del pannello: (chiave interna, etichetta, spiegazione del «?»)
    STATUS_ROWS = [
        ("sdr",    "Ricevitore SDR",
         "La radio è aperta e il flowgraph sta girando."),
        ("signal", "Segnale in arrivo",
         "Il decoder riceve campioni e misura lo scostamento di frequenza (AFC). "
         "Se resta spento: frequenza sbagliata, guadagno troppo basso o antenna scollegata."),
        ("sync",   "Sincronizzazione TETRA",
         "Il decoder ha agganciato la struttura delle trame TETRA e legge i "
         "messaggi di rete. È il segno che sei davvero su un canale di controllo."),
        ("net",    "Rete rilevata",
         "MCC (Paese), MNC (operatore), CC (codice colore) e LA (area) letti "
         "dai messaggi di rete della cella."),
        ("crypt",  "Traffico cifrato",
         "Via etere TETRA segnala SE il traffico è cifrato, non QUALE algoritmo. "
         "L'algoritmo (TEA1…TEA7) lo scegli tu nell'editor delle chiavi."),
        ("key",    "Chiavi configurate",
         "Quante chiavi contiene il keyfile e per quale rete: serve solo per "
         "decifrare traffico che sei autorizzato a decifrare."),
    ]

    def _build_status_box(self):
        box = QGroupBox("Stato")
        grid = QFormLayout(box)
        self._status_rows = {}
        for key, label, tip in self.STATUS_ROWS:
            mark = QLabel("·")
            mark.setFixedWidth(16)
            mark.setAlignment(Qt.AlignCenter)
            text = QLabel("—")
            text.setWordWrap(True)
            row = QWidget()
            h = QHBoxLayout(row); h.setContentsMargins(0, 0, 0, 0)
            h.addWidget(mark); h.addWidget(text, 1)
            name = QLabel(f"{label}:")
            name.setToolTip(tip)
            row.setToolTip(tip)
            grid.addRow(name, row)
            self._status_rows[key] = (mark, text)
        return box

    def _set_status_row(self, key, ok, text):
        """ok: True → ✓ verde, False → ! ambra, None → · grigio (non pertinente)."""
        mark, lbl = self._status_rows[key]
        if ok is True:
            mark.setText("✓"); mark.setStyleSheet("color:#2e9e5b; font-weight:bold;")
        elif ok is False:
            mark.setText("!"); mark.setStyleSheet("color:#c9781a; font-weight:bold;")
        else:
            mark.setText("·"); mark.setStyleSheet("color: palette(mid);")
        lbl.setText(text)

    def _refresh_status(self):
        """Aggiorna il pannello Stato: una riga per ogni cosa che può mancare.
        Gira anche a catena ferma, così le chiavi si vedono comunque."""
        st = self.tap.snapshot() if self.tap else StatusTap._empty()
        now = time.time()
        fresh = lambda ts: ts and (now - ts) < 10       # noqa: E731 — leggibile così

        running = bool(self._procs)
        if not running:
            self._set_status_row("sdr", None, "catena ferma")
            self._set_status_row("signal", None, "—")
            self._set_status_row("sync", None, "—")
            self._set_status_row("net", None, "—")
            self._set_status_row("crypt", None, "—")
        else:
            self._set_status_row("sdr", True, "radio aperta, flowgraph attivo")
            if fresh(st["signal_ts"]):
                self._set_status_row("signal", True, "il decoder riceve campioni")
            else:
                self._set_status_row("signal", False,
                                     "nessun campione: controlla frequenza, guadagno e antenna")
            if fresh(st["sync_ts"]):
                self._set_status_row("sync", True, "agganciato al canale di controllo")
            else:
                self._set_status_row("sync", False,
                                     "non agganciato: sei forse su un canale che non è di controllo")
            if st["mcc"] is not None:
                bits = [f"MCC {st['mcc']}", f"MNC {st['mnc']}"]
                if st["ccode"] is not None:
                    bits.append(f"CC {st['ccode']}")
                if st["la"] is not None:
                    bits.append(f"LA {st['la']}")
                if st["control"]:
                    bits.append(f"↓ {st['control']:.4f} MHz")
                self._set_status_row("net", True, " · ".join(bits))
            else:
                self._set_status_row("net", False, "nessuna rete letta finora")
            if fresh(st["enc_ts"]) or st["crypt"] >= 2:
                self._set_status_row("crypt", False,
                                     "sì — l'aria dice solo CHE è cifrato, non con quale algoritmo")
            elif st["crypt"] == 1:
                self._set_status_row("crypt", True, "no, traffico in chiaro")
            else:
                self._set_status_row("crypt", None, "non ancora determinato")

        # le chiavi si leggono dal file: informazione valida anche a catena ferma
        net, keys = parse_keyfile(KEYFILE)
        if keys:
            algo = dict((v, k) for k, v in KSG_TYPES).get(
                int(net.get("ksg_type", 0) or 0), "?")
            summary = (f"{len(keys)} per MCC {net.get('mcc', '?')} / MNC "
                       f"{net.get('mnc', '?')} · algoritmo scelto: {algo}")
            self._set_status_row("key", True, summary)
            self.keys_summary.setText(
                f"<b>{len(keys)}</b> chiave/i configurate per <b>MCC "
                f"{net.get('mcc', '?')} / MNC {net.get('mnc', '?')}</b>, algoritmo "
                f"scelto <b>{algo}</b>, classe di sicurezza "
                f"{net.get('security_class', '?')}.")
        else:
            self._set_status_row("key", None,
                                 "nessuna — servono solo per decifrare, apri «Chiavi»")
            self.keys_summary.setText(
                "Nessuna chiave configurata: sentirai <b>solo le chiamate in "
                "chiaro</b>. Apri l'editor per inserire le tue.")

        self._refresh_network(st)

    def _refresh_network(self, st):
        """Riempie la scheda Rete con l'ultimo stato letto."""
        def show(key, value):
            self._net_fields[key].setText("—" if value in (None, "") else str(value))

        show("mcc", st["mcc"])
        show("mnc", st["mnc"])
        show("ccode", st["ccode"])
        show("la", st["la"])
        show("control", f"{st['control']:.4f} MHz" if st["control"] else None)
        if st["crypt"] >= 2:
            show("crypt", "sì (l'algoritmo non è deducibile dall'aria)")
        elif st["crypt"] == 1:
            show("crypt", "no, traffico in chiaro")
        else:
            show("crypt", None)
        seen = max(st["sync_ts"], st["signal_ts"])
        show("seen", datetime.fromtimestamp(seen).strftime("%H:%M:%S") if seen else None)

    def _detected_net(self):
        """(mcc, mnc) letti dall'aria, o None: alimenta «Usa rete rilevata»."""
        st = self.tap.snapshot() if self.tap else None
        if st and st["mcc"] is not None:
            return st["mcc"], st["mnc"]
        return None

    # -- modalità Base / Avanzata -----------------------------------------

    def _apply_mode(self, *_):
        advanced = self.mode_combo.currentText() == "Avanzata"
        remote = self.sdr_kind.currentData() == "remote"
        self._row_visible(self.form, self.remote_w, remote)
        # in Base la scheda «Avanzate» non si vede proprio: meno cose, meno dubbi
        self.tabs.setTabVisible(self.adv_tab_index, advanced)

    @staticmethod
    def _row_visible(form, field, visible):
        field.setVisible(visible)
        lbl = form.labelForField(field)
        if lbl is not None:
            lbl.setVisible(visible)

    def _check_raster(self, mhz):
        """I canali TETRA stanno su multipli di 25 kHz. Se la frequenza cade in
        mezzo, il decoder non aggancia nulla pur vedendo il segnale: meglio
        dirlo subito, invece di lasciar cercare l'errore altrove."""
        khz = round(mhz * 1000, 3)
        off = abs(khz % 25.0)
        off = min(off, 25.0 - off)
        if off < 0.001:
            self.freq_hint.setText("")
            return
        near = round(khz / 25.0) * 25.0 / 1000.0
        self.freq_hint.setText(
            f"⚠ {mhz:.4f} MHz non è sul reticolo dei canali TETRA (25 kHz): "
            f"sei a {off:.1f} kHz dal canale più vicino, <b>{near:.4f} MHz</b>. "
            f"Se non decodifichi, prova quello.")
        self.freq_hint.setStyleSheet("color:#c9781a;")

    # -- profili di configurazione ----------------------------------------

    #: campi salvati in un profilo (mai chiavi, mai percorsi di sistema)
    def _collect_config(self):
        return {
            "freq": self.freq.value(),
            "gain": self.gain.value(),
            "ppm": self.ppm.value(),
            "sdr_kind": self.sdr_kind.currentData(),
            "remote_ip": self.remote_ip.text().strip(),
            "remote_port": self.remote_port.value(),
            "device": self.device.currentText().strip(),
            "spectrum": self.show_spectrum.isChecked(),
            "mode": self.mode_combo.currentText(),
        }

    def _apply_config(self, cfg):
        self.freq.setValue(float(cfg.get("freq", 390.5)))
        self.gain.setValue(int(cfg.get("gain", 38)))
        self.ppm.setValue(float(cfg.get("ppm", 0.0)))
        idx = self.sdr_kind.findData(cfg.get("sdr_kind", "local"))
        self.sdr_kind.setCurrentIndex(idx if idx >= 0 else 0)
        self.remote_ip.setText(str(cfg.get("remote_ip", "192.168.64.1")))
        self.remote_port.setValue(int(cfg.get("remote_port", 1234)))
        self.device.setEditText(str(cfg.get("device", "")))
        self.show_spectrum.setChecked(bool(cfg.get("spectrum", True)))
        mode = cfg.get("mode", "Base")
        self.mode_combo.setCurrentIndex(1 if mode == "Avanzata" else 0)
        self._apply_mode()

    @staticmethod
    def _read_profiles():
        try:
            data = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _load_profiles(self):
        self._profiles = self._read_profiles()
        self.profile_combo.clear()
        self.profile_combo.addItem("— nessun profilo —")
        for name in sorted(self._profiles):
            self.profile_combo.addItem(name)

    def _apply_profile(self, index):
        if index <= 0:
            return
        cfg = self._profiles.get(self.profile_combo.itemText(index))
        if cfg:
            self._apply_config(cfg)
            self._log(f"[launcher] profilo «{self.profile_combo.itemText(index)}» applicato.")

    def _save_profile(self):
        current = self.profile_combo.currentText()
        suggested = current if self.profile_combo.currentIndex() > 0 else ""
        name, ok = QInputDialog.getText(self, "Salva profilo",
                                        "Nome del profilo:", text=suggested)
        name = name.strip()
        if not ok or not name:
            return
        self._profiles[name] = self._collect_config()
        if not self._write_profiles():
            return
        self._load_profiles()
        self.profile_combo.setCurrentIndex(max(0, self.profile_combo.findText(name)))
        self._log(f"[launcher] profilo «{name}» salvato in {PROFILES_FILE}")

    def _delete_profile(self):
        index = self.profile_combo.currentIndex()
        if index <= 0:
            QMessageBox.information(self, "Nessun profilo",
                                    "Scegli prima un profilo dall'elenco.")
            return
        name = self.profile_combo.itemText(index)
        if QMessageBox.question(self, "Elimino?", f"Elimino il profilo «{name}»?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._profiles.pop(name, None)
        if self._write_profiles():
            self._load_profiles()

    def _write_profiles(self) -> bool:
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            PROFILES_FILE.write_text(
                json.dumps(self._profiles, indent=2, ensure_ascii=False), encoding="utf-8")
            return True
        except OSError as exc:
            QMessageBox.critical(self, "Errore",
                                 f"Impossibile scrivere {PROFILES_FILE}:\n{exc}")
            return False

    # -- dettagli rete e diagnostica --------------------------------------

    def _network_text(self):
        """I dati della rete come testo, per gli appunti e la diagnostica."""
        lines = ["Rete TETRA rilevata da OsmoTetra"]
        for key, label, _ in self.NET_FIELDS:
            lines.append(f"{label}: {self._net_fields[key].text()}")
        return "\n".join(lines) + "\n"

    def _copy_network(self):
        QApplication.clipboard().setText(self._network_text())
        self._log("[launcher] dettagli della rete copiati negli appunti.")

    def _diagnostics_text(self):
        """Rapporto di diagnostica. NON contiene chiavi: il keyfile compare solo
        come conteggio, e dal log il materiale di chiave viene rimosso."""
        cfg = self._collect_config()
        net, keys = parse_keyfile(KEYFILE)
        out = ["OsmoTetra — diagnostica",
               f"Generata il: {datetime.now():%Y-%m-%d %H:%M:%S}",
               "Questo file NON contiene alcuna chiave di decifratura.",
               "", "== Sistema =="]
        out.append(f"Python (pannello): {sys.version.split()[0]}")
        for label, cmd in (("Sistema", ["bash", "-lc",
                                        ". /etc/os-release 2>/dev/null && echo \"$PRETTY_NAME\""]),
                           ("GNU Radio", ["gnuradio-config-info", "-v"]),
                           ("socat", ["bash", "-lc", "socat -V 2>&1 | head -2 | tail -1"])):
            out.append(f"{label}: {self._run_brief(cmd)}")

        out += ["", "== Impostazioni =="]
        for k, v in cfg.items():
            out.append(f"{k}: {v}")
        out.append(f"device_args effettivi: {self._device_args() or '(automatico)'}")

        out += ["", "== Componenti =="]
        for label, path in (("flowgraph", FLOWGRAPH), ("tetra-rx", OSMO_SRC / "tetra-rx"),
                            ("receiver1udp", OSMO_SRC / "receiver1udp"),
                            ("demodulatore", OSMO_SRC / "demod" / "simdemod3_telive.py"),
                            ("telive", TELIVE_DIR / "telive"), ("keyfile", KEYFILE)):
            out.append(f"{label}: {path} — {'presente' if Path(path).exists() else 'MANCANTE'}")

        out += ["", "== Stato =="]
        out.append(f"catena in esecuzione: {'sì' if self._procs else 'no'}")
        for key, label, _ in self.STATUS_ROWS:
            mark, text = self._status_rows[key]
            out.append(f"[{mark.text()}] {label}: {text.text()}")

        out += ["", "== Rete ==", self._network_text().strip()]

        out += ["", "== Chiavi (solo conteggio) ==",
                f"chiavi nel keyfile: {len(keys)}",
                f"rete del keyfile: MCC {net.get('mcc', '—')} / MNC {net.get('mnc', '—')}",
                f"ksg_type: {net.get('ksg_type', '—')} · "
                f"security_class: {net.get('security_class', '—')}"]

        out += ["", "== Log (ultime 300 righe, chiavi rimosse) =="]
        out += [redact_keys(t) for _, t in self._log_lines[-300:]]
        return "\n".join(out) + "\n"

    @staticmethod
    def _run_brief(cmd):
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return (res.stdout.strip() or res.stderr.strip() or "?").splitlines()[0]
        except (OSError, subprocess.SubprocessError, IndexError):
            return "non disponibile"

    def _export_diagnostics(self):
        default = str(Path.home() / f"osmotetra-diagnostica-{datetime.now():%Y%m%d-%H%M%S}.txt")
        path, _ = QFileDialog.getSaveFileName(
            self, "Esporta diagnostica", default, "File di testo (*.txt)")
        if not path:
            return
        try:
            Path(path).write_text(self._diagnostics_text(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Errore", f"Impossibile scrivere {path}:\n{exc}")
            return
        QMessageBox.information(
            self, "Diagnostica salvata",
            f"Salvata in:\n{path}\n\nContiene versioni, impostazioni, stato e log "
            f"(con le chiavi rimosse). Puoi allegarla quando chiedi aiuto.")
        self._log(f"[launcher] diagnostica esportata in {path}")

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
                  self.sdr_kind, self.remote_ip, self.remote_port, self.mode_combo,
                  self.profile_combo):
            w.setEnabled(not running)
        if running:
            self.status.setText("In esecuzione — guarda la finestra di telive")
            self.status.setStyleSheet("color: white; background:#2e9e5b; padding:6px; border-radius:4px;")
        else:
            self.status.setText("Fermo")
            self.status.setStyleSheet("color: white; background:#9aa0a6; padding:6px; border-radius:4px;")

    def open_keys(self):
        KeyEditor(KEYFILE, self, detected=self._detected_net()).exec_()
        self._refresh_status()   # le chiavi possono essere cambiate

    # -- log a due livelli -------------------------------------------------

    #: parole che rendono «importante» anche una riga grezza di flowgraph/decoder
    #: (in inglese: sono i messaggi di libreria — tetra-rx, gr-osmosdr, python — non
    #: i nostri, che si riconoscono invece dal tag [osmotetra_rx] qui sotto)
    LOG_ALERTS = ("error", "traceback", "fail", "not found", "no devices",
                  "permission denied", "cannot")
    #: rumore noto e innocuo che NON deve passare, pur contenendo parole d'allarme
    #: (RtAudio sonda le periferiche audio ad ogni avvio: non c'entra con l'SDR)
    LOG_BENIGN = ("rtapi::getdeviceinfo",)

    @classmethod
    def _log_important(cls, text: str) -> bool:
        """Vero per le righe che vale la pena mostrare anche a log semplice:
        i nostri messaggi [launcher] e [osmotetra_rx] (già scritti per l'utente,
        in italiano) e qualunque riga grezza che segnali un guaio."""
        if text.startswith("[launcher]") or "[osmotetra_rx]" in text:
            return True
        low = text.lower()
        if any(word in low for word in cls.LOG_BENIGN):
            return False
        return any(word in low for word in cls.LOG_ALERTS)

    def _append_log(self, text: str):
        text = text.rstrip("\n")
        important = self._log_important(text)
        self._log_lines.append((important, text))
        if len(self._log_lines) > 4000:
            del self._log_lines[:2000]
        if important or self.log_tech.isChecked():
            self.log.appendPlainText(text)

    def _rerender_log(self, *_):
        tech = self.log_tech.isChecked()
        self.log.setPlainText("\n".join(
            t for important, t in self._log_lines if tech or important))
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def _clear_log(self):
        self._log_lines.clear()
        self.log.clear()

    def _log(self, text: str):
        self._emitter.line.emit(text)

    # -- avvio della catena ----------------------------------------------

    def on_start(self):
        problem = self._preflight()
        if problem:
            QMessageBox.critical(self, "Manca qualcosa", problem)
            return

        self._clear_log()
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

        # 3) tap dello stato (trasparente): riceve dal decoder e inoltra a telive.
        #    Se non riesce a mettersi in ascolto, si prosegue senza diagnostica e
        #    il decoder parla direttamente a telive (7379): la ricezione non cambia.
        self.tap = StatusTap()
        hack_port = TAP_PORT if self.tap.start() else TELIVE_UDP_PORT
        if hack_port == TAP_PORT:
            self._log(f"[launcher] stato/diagnostica attivi (tap {TAP_PORT} → telive {TELIVE_UDP_PORT})")
        else:
            self._log("[launcher] tap dello stato non disponibile: proseguo senza diagnostica")
            self.tap = None

        # 4) ricevitore: socat | simdemod3_telive.py | tetra-rx  (come receiver1udp,
        #    ma con TETRA_HACK_PORT verso il tap quando è attivo)
        self._log(f"$ socat | simdemod3_telive.py | tetra-rx   (TETRA_HACK_PORT={hack_port})")
        # Il demodulatore gira con lo STESSO interprete del flowgraph: è quello
        # che ha di sicuro i binding GNU Radio (vedi OSMOTETRA_PYTHON).
        pipeline = ('export TETRA_HACK_PORT="$1" TETRA_HACK_IP=127.0.0.1 TETRA_HACK_RXID=1; '
                    'socat -b 4096 UDP-RECV:42001 STDOUT | "$2" demod/simdemod3_telive.py | '
                    './tetra-rx -r -k sample_keyfile -s /dev/stdin')
        try:
            rx = subprocess.Popen(
                ["bash", "-c", pipeline, "_", str(hack_port), GR_PYTHON], cwd=str(OSMO_SRC),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, start_new_session=True)
        except OSError as exc:
            self.on_stop()
            QMessageBox.critical(self, "Errore", f"Impossibile avviare il ricevitore:\n{exc}")
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
        if self.tap is not None:
            self.tap.stop()
            self.tap = None
        for proc in (self._telive_proc, *reversed(self._procs)):
            _terminate(proc)
        # gnome-terminal apre telive in un processo server: il nostro handle è
        # già uscito, quindi chiudiamo telive per nome (best-effort).
        subprocess.run(["pkill", "-x", "telive"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._telive_proc = None
        self._procs.clear()
        self._set_running(False)
        self._refresh_status()
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
