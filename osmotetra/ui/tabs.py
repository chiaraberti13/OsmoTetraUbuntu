"""Schede di configurazione.

Ogni scheda espone ``load(cfg)`` e ``collect(cfg)``: la prima riempie i campi
dalla configurazione, la seconda fa il percorso inverso.

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .. import deps
from ..config import MAX_CHANNELS, Channel, Config
from .widgets import KHzSpinBox, MHzSpinBox, hint

#: Dispositivi noti a gr-osmosdr, con la stringa di argomenti corrispondente.
DEVICE_PRESETS = [
    ("RTL-SDR (prima chiavetta)", "rtl=0"),
    ("RTL-SDR (seconda chiavetta)", "rtl=1"),
    ("HackRF", "hackrf=0"),
    ("Airspy", "airspy=0"),
    ("SDRplay (richiede i driver del produttore)", "sdrplay=0"),
    ("USRP / UHD", "uhd"),
    ("Rilevamento automatico", ""),
]


class SdrTab(QWidget):
    """Parametri del ricevitore radio."""

    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.device = QComboBox()
        self.device.setEditable(True)
        for label, args in DEVICE_PRESETS:
            self.device.addItem(label, args)
        self.device.currentIndexChanged.connect(self._preset_selected)
        # Con argomenti vuoti gr-osmosdr sceglie da sé il primo dispositivo
        # disponibile: il campo vuoto non è un errore, va solo spiegato.
        self.device.lineEdit().setPlaceholderText(
            "vuoto = primo dispositivo disponibile")

        self.freq = MHzSpinBox(minimum=1.0, maximum=6000.0)
        self.samp_rate = QDoubleSpinBox()
        self.samp_rate.setRange(0.1, 61.44)
        self.samp_rate.setDecimals(3)
        self.samp_rate.setSuffix(" Ms/s")
        self.samp_rate.setSingleStep(0.1)
        self.samp_rate.setKeyboardTracking(False)

        self.first_decim = QSpinBox()
        self.first_decim.setRange(1, 4096)

        self.lowpass = QDoubleSpinBox()
        self.lowpass.setRange(1.0, 1000.0)
        self.lowpass.setDecimals(1)
        self.lowpass.setSuffix(" kHz")

        self.gain = QDoubleSpinBox()
        self.gain.setRange(0, 100)
        self.gain.setSuffix(" dB")
        self.if_gain = QDoubleSpinBox()
        self.if_gain.setRange(0, 100)
        self.if_gain.setSuffix(" dB")
        self.bb_gain = QDoubleSpinBox()
        self.bb_gain.setRange(0, 100)
        self.bb_gain.setSuffix(" dB")

        self.ppm = QDoubleSpinBox()
        self.ppm.setRange(-200, 200)
        self.ppm.setDecimals(2)
        self.ppm.setSuffix(" ppm")

        self.derived = QLabel()
        self.derived.setStyleSheet("color: palette(mid);")

        self.source = QComboBox()
        self.source.addItem("Radio SDR", "osmosdr")
        self.source.addItem("File IQ (prova senza radio)", "file")
        self.source.addItem("Sorgente nulla (prova della catena)", "null")
        self.source.currentIndexChanged.connect(self._source_changed)

        self.source_file = QLineEdit()
        self.source_file.setPlaceholderText("percorso di un file .cfile / .iq")
        self.browse = QPushButton("Sfoglia...")
        self.browse.clicked.connect(self._browse)
        self.repeat = QCheckBox("Ricomincia da capo alla fine del file")

        radio_box = QGroupBox("Ricevitore")
        radio_form = QFormLayout(radio_box)
        radio_form.addRow("Dispositivo:", self.device)
        radio_form.addRow("Frequenza centrale:", self.freq)
        radio_form.addRow("Campionamento:", self.samp_rate)
        radio_form.addRow("Decimazione:", self.first_decim)
        radio_form.addRow("Filtro di canale:", self.lowpass)
        radio_form.addRow("", self.derived)

        gain_box = QGroupBox("Guadagni e correzione")
        gain_form = QFormLayout(gain_box)
        gain_form.addRow("Guadagno RF:", self.gain)
        gain_form.addRow("Guadagno IF:", self.if_gain)
        gain_form.addRow("Guadagno banda base:", self.bb_gain)
        gain_form.addRow("Correzione:", self.ppm)
        gain_form.addRow("", hint(
            "Regola la correzione in ppm finché il valore AFC mostrato da "
            "telive nella finestra delle frequenze (tasto t) non è vicino a zero."
        ))

        source_box = QGroupBox("Sorgente del segnale")
        source_form = QFormLayout(source_box)
        source_form.addRow("Sorgente:", self.source)
        file_row = QHBoxLayout()
        file_row.addWidget(self.source_file, 1)
        file_row.addWidget(self.browse)
        source_form.addRow("File IQ:", file_row)
        source_form.addRow("", self.repeat)
        source_form.addRow("", hint(
            "Le sorgenti di prova permettono di verificare l'intera catena "
            "senza avere una radio collegata."
        ))

        layout = QVBoxLayout(self)
        layout.addWidget(radio_box)
        layout.addWidget(gain_box)
        layout.addWidget(source_box)
        layout.addStretch(1)

        for widget in (self.freq, self.samp_rate, self.first_decim, self.lowpass,
                       self.gain, self.if_gain, self.bb_gain, self.ppm):
            widget.valueChanged.connect(self._on_change)
        self.device.currentTextChanged.connect(self._on_change)
        self.source_file.textChanged.connect(self._on_change)

    # -- eventi ------------------------------------------------------------

    def _on_change(self, *_args) -> None:
        self._update_derived()
        self.changed.emit()

    def _preset_selected(self, index: int) -> None:
        args = self.device.itemData(index)
        if args is not None:
            self.device.setEditText(args)

    def _source_changed(self, *_args) -> None:
        is_file = self.source.currentData() == "file"
        self.source_file.setEnabled(is_file)
        self.browse.setEnabled(is_file)
        self.repeat.setEnabled(is_file)
        self.changed.emit()

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Scegli un file IQ", "", "File IQ (*.cfile *.iq *.raw);;Tutti (*)"
        )
        if path:
            self.source_file.setText(path)

    def _update_derived(self) -> None:
        decim = self.first_decim.value() or 1
        if_rate = self.samp_rate.value() * 1e6 / decim
        needed = 2 * self.lowpass.value() * 1e3
        text = (f"Dopo la decimazione: {if_rate / 1e3:.1f} kHz "
                f"(servono almeno {needed / 1e3:.1f} kHz per il canale)")
        if if_rate < needed:
            text += "  ⚠"
        self.derived.setText(text)

    # -- configurazione ----------------------------------------------------

    def load(self, cfg: Config) -> None:
        sdr = cfg.sdr
        self.device.setEditText(sdr.device_args)
        self.freq.set_hz(sdr.freq_hz)
        self.samp_rate.setValue(sdr.samp_rate / 1e6)
        self.first_decim.setValue(sdr.first_decim)
        self.lowpass.setValue(sdr.lowpass_hz / 1e3)
        self.gain.setValue(sdr.gain)
        self.if_gain.setValue(sdr.if_gain)
        self.bb_gain.setValue(sdr.bb_gain)
        self.ppm.setValue(sdr.ppm)
        self.repeat.setChecked(sdr.repeat_file)

        if sdr.source.startswith("file:"):
            self.source.setCurrentIndex(self.source.findData("file"))
            self.source_file.setText(sdr.source[len("file:"):])
        else:
            index = self.source.findData(sdr.source)
            self.source.setCurrentIndex(index if index >= 0 else 0)
        self._source_changed()
        self._update_derived()

    def collect(self, cfg: Config) -> None:
        sdr = cfg.sdr
        sdr.device_args = self.device.currentText().strip()
        sdr.freq_hz = self.freq.hz()
        sdr.samp_rate = self.samp_rate.value() * 1e6
        sdr.first_decim = self.first_decim.value()
        sdr.lowpass_hz = self.lowpass.value() * 1e3
        sdr.gain = self.gain.value()
        sdr.if_gain = self.if_gain.value()
        sdr.bb_gain = self.bb_gain.value()
        sdr.ppm = self.ppm.value()
        sdr.repeat_file = self.repeat.isChecked()

        kind = self.source.currentData()
        if kind == "file":
            sdr.source = f"file:{self.source_file.text().strip()}"
        else:
            sdr.source = kind


class ChannelsTab(QWidget):
    """Canali: offset, frequenza risultante, porte, opzioni di tetra-rx."""

    changed = pyqtSignal()

    COLUMNS = ["Attivo", "Offset", "Frequenza", "Porta UDP",
               "Ricomponi (-r)", "SDS testo (-s)", "Cifrati (-e)"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._base_freq_hz = 0.0
        self._base_port = 42000
        self._loading = False

        self.count = QSpinBox()
        self.count.setRange(1, MAX_CHANNELS)
        self.count.valueChanged.connect(self._count_changed)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)

        top = QHBoxLayout()
        top.addWidget(QLabel("Numero di canali:"))
        top.addWidget(self.count)
        top.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.table, 1)
        layout.addWidget(hint(
            "Ogni canale usa una porta UDP propria e un proprio decoder. "
            "Il canale 1 conviene sintonizzarlo sul canale di controllo, che "
            "porta la maggior parte della segnalazione. Più canali significano "
            "più carico di CPU: sono i decoder, non la radio, a consumarla."
        ))

    # -- costruzione righe -------------------------------------------------

    def _count_changed(self, value: int) -> None:
        while self.table.rowCount() < value:
            self._add_row()
        while self.table.rowCount() > value:
            self.table.removeRow(self.table.rowCount() - 1)
        self._refresh_derived()
        if not self._loading:
            self.changed.emit()

    def _add_row(self) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        enabled = QCheckBox()
        enabled.setChecked(True)
        enabled.stateChanged.connect(self._on_edit)
        self.table.setCellWidget(row, 0, _centered(enabled))

        offset = KHzSpinBox()
        offset.valueChanged.connect(self._on_edit)
        self.table.setCellWidget(row, 1, offset)

        freq_item = QTableWidgetItem("")
        freq_item.setFlags(Qt.ItemIsEnabled)
        self.table.setItem(row, 2, freq_item)

        port_item = QTableWidgetItem("")
        port_item.setFlags(Qt.ItemIsEnabled)
        self.table.setItem(row, 3, port_item)

        for column, checked in ((4, True), (5, True), (6, False)):
            box = QCheckBox()
            box.setChecked(checked)
            box.stateChanged.connect(self._on_edit)
            self.table.setCellWidget(row, column, _centered(box))

    def _widget(self, row: int, column: int):
        cell = self.table.cellWidget(row, column)
        if isinstance(cell, KHzSpinBox):
            return cell
        return cell.findChild(QCheckBox) if cell else None

    def _on_edit(self, *_args) -> None:
        self._refresh_derived()
        if not self._loading:
            self.changed.emit()

    # -- valori derivati ---------------------------------------------------

    def set_context(self, base_freq_hz: float, base_port: int) -> None:
        """Aggiorna frequenza centrale e porta base usate nelle colonne calcolate."""
        self._base_freq_hz = base_freq_hz
        self._base_port = base_port
        self._refresh_derived()

    def _refresh_derived(self) -> None:
        for row in range(self.table.rowCount()):
            offset = self._widget(row, 1)
            if offset is None:
                continue
            freq = (self._base_freq_hz + offset.hz()) / 1e6
            self.table.item(row, 2).setText(f"{freq:.4f} MHz")
            self.table.item(row, 3).setText(str(self._base_port + row + 1))

    # -- configurazione ----------------------------------------------------

    def load(self, cfg: Config) -> None:
        self._loading = True
        try:
            self.count.setValue(len(cfg.channels))
            self._count_changed(len(cfg.channels))
            for row, channel in enumerate(cfg.channels):
                self._widget(row, 0).setChecked(channel.enabled)
                self._widget(row, 1).set_hz(channel.offset_hz)
                self._widget(row, 4).setChecked(channel.reassemble)
                self._widget(row, 5).setChecked(channel.sds_as_text)
                self._widget(row, 6).setChecked(channel.allow_encrypted)
            self.set_context(cfg.sdr.freq_hz, cfg.base_port)
        finally:
            self._loading = False

    def collect(self, cfg: Config) -> None:
        channels: list[Channel] = []
        for row in range(self.table.rowCount()):
            channels.append(Channel(
                offset_hz=self._widget(row, 1).hz(),
                enabled=self._widget(row, 0).isChecked(),
                reassemble=self._widget(row, 4).isChecked(),
                sds_as_text=self._widget(row, 5).isChecked(),
                allow_encrypted=self._widget(row, 6).isChecked(),
            ))
        cfg.channels = channels or [Channel()]


class TeliveTab(QWidget):
    """Impostazioni di telive e del controllo del ricevitore."""

    changed = pyqtSignal()

    #: Tasti che telive interpreta all'avvio (TETRA_KEYS).
    KEY_OPTIONS = [
        ("R", "Registra le chiamate"),
        ("l", "Scrivi il log della segnalazione"),
        ("m", "Silenzia gli SSI sconosciuti (mutessi)"),
        ("M", "Silenzia tutto l'audio"),
        ("a", "Mostra tutta la segnalazione (alldump)"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        self.udp_port = QSpinBox()
        self.udp_port.setRange(1, 65535)
        self.base_port = QSpinBox()
        self.base_port.setRange(1024, 65500)

        self.key_boxes: dict[str, QCheckBox] = {}
        keys_box = QGroupBox("All'avvio di telive")
        keys_layout = QVBoxLayout(keys_box)
        for key, label in self.KEY_OPTIONS:
            box = QCheckBox(f"{label}  ({key})")
            box.stateChanged.connect(self.changed)
            self.key_boxes[key] = box
            keys_layout.addWidget(box)

        self.ssi_filter = QLineEdit()
        self.ssi_filter.setPlaceholderText("es. 10??  oppure  +(1000|20??)")
        self.ssi_descriptions = QLineEdit()
        self.ssi_descriptions.setPlaceholderText("file con le descrizioni degli SSI")

        self.kml_enabled = QCheckBox("Scrivi le posizioni in formato KML")
        self.kml_interval = QSpinBox()
        self.kml_interval.setRange(1, 3600)
        self.kml_interval.setSuffix(" s")

        self.xmlrpc_enabled = QCheckBox(
            "Permetti a telive di controllare il ricevitore (XMLRPC)")
        self.auto_tune = QCheckBox(
            "Sintonizza automaticamente i canali liberi dalla segnalazione")
        self.ppm_autocorrect = QCheckBox(
            "Correggi automaticamente la deriva in ppm dai dati AFC")
        self.baseband_autocorrect = QCheckBox(
            "Sposta la frequenza centrale per coprire tutti i canali")
        self.scan_list = QLineEdit()
        self.scan_list.setPlaceholderText("390-395/12.5;420-430/12.5")

        net_box = QGroupBox("Porte")
        net_form = QFormLayout(net_box)
        net_form.addRow("Porta UDP di telive:", self.udp_port)
        net_form.addRow("Porta base del ricevitore:", self.base_port)
        net_form.addRow("", hint(
            "Il ricevitore usa la porta base per il controllo XMLRPC e le "
            "porte successive per i canali: con porta base 42000 il canale 1 "
            "arriva sulla 42001."
        ))

        filter_box = QGroupBox("Filtri e annotazioni")
        filter_form = QFormLayout(filter_box)
        filter_form.addRow("Filtro SSI:", self.ssi_filter)
        filter_form.addRow("Descrizioni SSI:", self.ssi_descriptions)
        filter_form.addRow(self.kml_enabled)
        filter_form.addRow("Aggiornamento KML:", self.kml_interval)

        rx_box = QGroupBox("Controllo del ricevitore")
        rx_layout = QVBoxLayout(rx_box)
        rx_layout.addWidget(self.xmlrpc_enabled)
        rx_layout.addWidget(self.auto_tune)
        rx_layout.addWidget(self.ppm_autocorrect)
        rx_layout.addWidget(self.baseband_autocorrect)
        scan_form = QFormLayout()
        scan_form.addRow("Intervalli di scansione:", self.scan_list)
        rx_layout.addLayout(scan_form)
        rx_layout.addWidget(hint(
            "Con il controllo attivo, telive può cambiare frequenza, guadagno "
            "e ppm da solo: i valori mostrati nella scheda SDR possono quindi "
            "differire da quelli impostati."
        ))

        layout = QVBoxLayout(self)
        layout.addWidget(net_box)
        layout.addWidget(keys_box)
        layout.addWidget(filter_box)
        layout.addWidget(rx_box)
        layout.addStretch(1)

        for widget in (self.udp_port, self.base_port, self.kml_interval):
            widget.valueChanged.connect(self.changed)
        for widget in (self.kml_enabled, self.xmlrpc_enabled, self.auto_tune,
                       self.ppm_autocorrect, self.baseband_autocorrect):
            widget.stateChanged.connect(self.changed)
        for widget in (self.ssi_filter, self.ssi_descriptions, self.scan_list):
            widget.textChanged.connect(self.changed)

    def load(self, cfg: Config) -> None:
        tc = cfg.telive
        self.udp_port.setValue(tc.udp_port)
        self.base_port.setValue(cfg.base_port)
        for key, box in self.key_boxes.items():
            box.setChecked(key in tc.keys)
        self.ssi_filter.setText(tc.ssi_filter)
        self.ssi_descriptions.setText(tc.ssi_descriptions)
        self.kml_enabled.setChecked(tc.kml_enabled)
        self.kml_interval.setValue(tc.kml_interval)
        self.xmlrpc_enabled.setChecked(tc.xmlrpc_enabled)
        self.auto_tune.setChecked(tc.auto_tune)
        self.ppm_autocorrect.setChecked(tc.ppm_autocorrect)
        self.baseband_autocorrect.setChecked(tc.baseband_autocorrect)
        self.scan_list.setText(tc.scan_list)

    def collect(self, cfg: Config) -> None:
        tc = cfg.telive
        tc.udp_port = self.udp_port.value()
        cfg.base_port = self.base_port.value()
        tc.keys = "".join(k for k, b in self.key_boxes.items() if b.isChecked())
        tc.ssi_filter = self.ssi_filter.text().strip()
        tc.ssi_descriptions = self.ssi_descriptions.text().strip()
        tc.kml_enabled = self.kml_enabled.isChecked()
        tc.kml_interval = self.kml_interval.value()
        tc.xmlrpc_enabled = self.xmlrpc_enabled.isChecked()
        tc.auto_tune = self.auto_tune.isChecked()
        tc.ppm_autocorrect = self.ppm_autocorrect.isChecked()
        tc.baseband_autocorrect = self.baseband_autocorrect.isChecked()
        tc.scan_list = self.scan_list.text().strip()


class SystemTab(QWidget):
    """Terminale, registrazione audio e stato delle dipendenze."""

    changed = pyqtSignal()
    install_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.terminal = QLineEdit()
        self.terminal.setPlaceholderText("vuoto = rilevamento automatico")
        self.columns = QSpinBox()
        self.columns.setRange(80, 400)
        self.rows = QSpinBox()
        self.rows.setRange(24, 200)
        self.font_name = QLineEdit()
        self.font_size = QSpinBox()
        self.font_size.setRange(4, 40)

        term_box = QGroupBox("Terminale di telive")
        term_form = QFormLayout(term_box)
        term_form.addRow("Comando:", self.terminal)
        size_row = QHBoxLayout()
        size_row.addWidget(self.columns)
        size_row.addWidget(QLabel("×"))
        size_row.addWidget(self.rows)
        size_row.addStretch(1)
        term_form.addRow("Dimensione:", size_row)
        font_row = QHBoxLayout()
        font_row.addWidget(self.font_name, 1)
        font_row.addWidget(self.font_size)
        term_form.addRow("Carattere:", font_row)
        term_form.addRow("", hint(
            "telive richiede 203×60 caratteri: sotto questa dimensione "
            "l'interfaccia risulta illeggibile. Su schermi piccoli conviene "
            "ridurre il corpo del carattere anziché la finestra."
        ))

        self.tetrad = QCheckBox(
            "Ricomprimi automaticamente le chiamate registrate in OGG")
        rec_box = QGroupBox("Registrazione")
        rec_layout = QVBoxLayout(rec_box)
        rec_layout.addWidget(self.tetrad)
        rec_layout.addWidget(hint(
            "Richiede il codec vocale ACELP. Le chiamate grezze finiscono in "
            "tetra/in, quelle convertite in tetra/out."
        ))

        self.deps_list = QLabel()
        self.deps_list.setTextFormat(Qt.RichText)
        self.deps_list.setWordWrap(True)
        self.deps_list.setTextInteractionFlags(Qt.TextSelectableByMouse)

        refresh = QPushButton("Ricontrolla")
        refresh.clicked.connect(self.refresh_deps)
        install_codec = QPushButton("Installa il codec vocale ACELP...")
        install_codec.clicked.connect(lambda: self.install_requested.emit("codec"))
        install_deps = QPushButton("Installa le dipendenze mancanti...")
        install_deps.clicked.connect(lambda: self.install_requested.emit("apt"))

        deps_box = QGroupBox("Dipendenze")
        deps_layout = QVBoxLayout(deps_box)
        deps_layout.addWidget(self.deps_list)
        button_row = QHBoxLayout()
        button_row.addWidget(refresh)
        button_row.addWidget(install_deps)
        button_row.addWidget(install_codec)
        button_row.addStretch(1)
        deps_layout.addLayout(button_row)

        layout = QVBoxLayout(self)
        layout.addWidget(term_box)
        layout.addWidget(rec_box)
        layout.addWidget(deps_box)
        layout.addStretch(1)

        for widget in (self.columns, self.rows, self.font_size):
            widget.valueChanged.connect(self.changed)
        for widget in (self.terminal, self.font_name):
            widget.textChanged.connect(self.changed)
        self.tetrad.stateChanged.connect(self.changed)

    def refresh_deps(self) -> None:
        rows = []
        for check in deps.run_checks():
            if check.ok:
                mark, color = "ok", "#2e9e5b"
            elif check.required:
                mark, color = "manca", "#cc3d3d"
            else:
                mark, color = "opzionale", "#e8a33d"
            rows.append(
                f'<tr><td><b style="color:{color}">{mark}</b></td>'
                f"<td>&nbsp;{check.name}&nbsp;</td>"
                f"<td>{check.detail}</td></tr>"
            )
        self.deps_list.setText("<table>" + "".join(rows) + "</table>")

    def load(self, cfg: Config) -> None:
        term = cfg.terminal
        self.terminal.setText(term.command)
        self.columns.setValue(term.columns)
        self.rows.setValue(term.rows)
        self.font_name.setText(term.font)
        self.font_size.setValue(term.font_size)
        self.tetrad.setChecked(cfg.recording.tetrad_enabled)

    def collect(self, cfg: Config) -> None:
        term = cfg.terminal
        term.command = self.terminal.text().strip()
        term.columns = self.columns.value()
        term.rows = self.rows.value()
        term.font = self.font_name.text().strip() or "Monospace"
        term.font_size = self.font_size.value()
        cfg.recording.tetrad_enabled = self.tetrad.isChecked()


def _centered(widget: QWidget) -> QWidget:
    """Incapsula un widget per centrarlo dentro una cella di tabella."""
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setAlignment(Qt.AlignCenter)
    layout.addWidget(widget)
    return container
