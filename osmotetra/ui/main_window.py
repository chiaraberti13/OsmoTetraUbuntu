"""Finestra principale di OsmoTetraUbuntu.

Un solo posto da cui: configurare i parametri, avviare e fermare la catena,
vedere lo stato dei processi e leggere i log.

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import subprocess

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QAction, QComboBox, QHBoxLayout, QInputDialog, QLabel, QMainWindow,
    QMessageBox, QPushButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget,
)

from .. import config as config_mod, deps, paths
from ..config import Config
from ..pipeline import Pipeline, StageState
from .log_view import LogView
from .tabs import ChannelsTab, SdrTab, SystemTab, TeliveTab
from .widgets import StatusLight, separator

#: Frequenza di aggiornamento dello stato dei processi.
POLL_INTERVAL_MS = 1000
#: Frequenza con cui si rileggono i parametri dal ricevitore via XMLRPC.
RX_POLL_INTERVAL_MS = 2000


class MainWindow(QMainWindow):
    """Finestra unica dell'applicazione."""

    #: Emesso dal thread di lettura dei log: serve a rientrare nel thread
    #: della GUI, perché i widget Qt non si possono toccare da altri thread.
    log_line = pyqtSignal(str, str)
    stage_state = pyqtSignal(str, object)

    def __init__(self, cfg: Config | None = None, parent=None):
        super().__init__(parent)
        self.cfg = cfg or Config.load()
        self.pipeline: Pipeline | None = None
        self._lights: dict[str, StatusLight] = {}
        self._pending_restart = False
        #: Attivo mentre si riempiono i widget dalla configurazione. Senza
        #: questa guardia i segnali valueChanged emessi durante il
        #: caricamento riscriverebbero la configurazione a partire da campi
        #: ancora vuoti, azzerandola.
        self._loading = False

        self.setWindowTitle("OsmoTetra — monitoraggio TETRA")
        self.resize(940, 760)

        self._build_ui()
        self._build_menu()
        self.load_config_into_widgets()
        self.system_tab.refresh_deps()

        self.log_line.connect(self._on_log_line)
        self.stage_state.connect(self._on_stage_state)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(POLL_INTERVAL_MS)

        self._rx_timer = QTimer(self)
        self._rx_timer.timeout.connect(self._poll_receiver)
        self._rx_timer.start(RX_POLL_INTERVAL_MS)

    # -- costruzione -------------------------------------------------------

    def _build_ui(self) -> None:
        self.start_button = QPushButton("Avvia")
        self.start_button.setDefault(True)
        self.start_button.clicked.connect(self.start_chain)

        self.stop_button = QPushButton("Ferma")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_chain)

        self.apply_button = QPushButton("Applica a caldo")
        self.apply_button.setEnabled(False)
        self.apply_button.setToolTip(
            "Invia al ricevitore frequenza, guadagni, ppm e offset senza "
            "fermare la catena."
        )
        self.apply_button.clicked.connect(self.apply_hot)

        self.profiles = QComboBox()
        self.profiles.setMinimumWidth(140)
        self._reload_profiles()
        self.profiles.activated.connect(self._profile_selected)

        save_profile = QPushButton("Salva profilo...")
        save_profile.clicked.connect(self._save_profile)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self.start_button)
        toolbar.addWidget(self.stop_button)
        toolbar.addWidget(self.apply_button)
        toolbar.addWidget(separator())
        toolbar.addWidget(QLabel("Profilo:"))
        toolbar.addWidget(self.profiles)
        toolbar.addWidget(save_profile)
        toolbar.addStretch(1)

        self.status_row = QHBoxLayout()
        self.status_row.addStretch(1)

        self.banner = QLabel()
        self.banner.setWordWrap(True)
        self.banner.setVisible(False)
        self.banner.setStyleSheet(
            "padding: 8px; border-radius: 4px;"
            "background: palette(alternate-base); border: 1px solid palette(mid);"
        )

        self.sdr_tab = SdrTab()
        self.channels_tab = ChannelsTab()
        self.telive_tab = TeliveTab()
        self.system_tab = SystemTab()
        self.log_view = LogView()

        self.tabs = QTabWidget()
        # Le schede di configurazione sono più alte di un portatile da 13":
        # senza area di scorrimento gli ultimi campi resterebbero tagliati e
        # irraggiungibili. Il log gestisce già il proprio scorrimento.
        self.tabs.addTab(_scrollable(self.sdr_tab), "Radio")
        self.tabs.addTab(self.channels_tab, "Canali")
        self.tabs.addTab(_scrollable(self.telive_tab), "telive")
        self.tabs.addTab(_scrollable(self.system_tab), "Sistema")
        self.tabs.addTab(self.log_view, "Log")

        for tab in (self.sdr_tab, self.channels_tab, self.telive_tab, self.system_tab):
            tab.changed.connect(self._on_config_changed)
        self.system_tab.install_requested.connect(self._run_installer)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(toolbar)
        layout.addLayout(self.status_row)
        layout.addWidget(self.banner)
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        self.statusBar().showMessage("Pronto")

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        save = QAction("&Salva configurazione", self)
        save.setShortcut("Ctrl+S")
        save.triggered.connect(self.save_config)
        file_menu.addAction(save)

        show_cmd = QAction("Mostra i &comandi equivalenti", self)
        show_cmd.triggered.connect(self._show_cmdline)
        file_menu.addAction(show_cmd)

        file_menu.addSeparator()
        quit_action = QAction("&Esci", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        help_menu = self.menuBar().addMenu("&Aiuto")
        about = QAction("&Informazioni", self)
        about.triggered.connect(self._about)
        help_menu.addAction(about)

    # -- configurazione <-> widget -----------------------------------------

    def load_config_into_widgets(self) -> None:
        self._loading = True
        try:
            for tab in (self.sdr_tab, self.channels_tab,
                        self.telive_tab, self.system_tab):
                tab.load(self.cfg)
        finally:
            self._loading = False
        self.channels_tab.set_context(self.cfg.sdr.freq_hz, self.cfg.base_port)
        self._refresh_banner()

    def collect_widgets_into_config(self) -> None:
        for tab in (self.sdr_tab, self.channels_tab, self.telive_tab, self.system_tab):
            tab.collect(self.cfg)

    def save_config(self) -> None:
        self.collect_widgets_into_config()
        path = self.cfg.save()
        self.statusBar().showMessage(f"Configurazione salvata in {path}", 4000)

    def _on_config_changed(self) -> None:
        if self._loading:
            return
        self.collect_widgets_into_config()
        # La scheda dei canali mostra le frequenze assolute: dipendono dalla
        # frequenza centrale e dalla porta base, che stanno in altre schede.
        self.channels_tab.set_context(self.cfg.sdr.freq_hz, self.cfg.base_port)
        self._refresh_banner()
        if self._is_running():
            self._pending_restart = True
            self.apply_button.setEnabled(True)

    def _refresh_banner(self) -> None:
        problems = self.cfg.validate()
        warnings = self.cfg.warnings()
        messages = []
        if problems:
            messages.append("<b>Da correggere prima di avviare:</b><br>"
                            + "<br>".join(f"• {p}" for p in problems))
        if warnings:
            messages.append("<b>Avvisi:</b><br>"
                            + "<br>".join(f"• {w}" for w in warnings))
        if self._pending_restart:
            messages.append(
                "<b>Alcune modifiche richiedono un riavvio</b> della catena "
                "(numero di canali, porte, dispositivo, campionamento). "
                "«Applica a caldo» aggiorna solo frequenza, guadagni, ppm e offset."
            )

        self.banner.setText("<br><br>".join(messages))
        self.banner.setVisible(bool(messages))
        self.start_button.setEnabled(not problems and not self._is_running())

    # -- profili -----------------------------------------------------------

    def _reload_profiles(self) -> None:
        current = self.profiles.currentText()
        self.profiles.clear()
        self.profiles.addItem("(nessuno)")
        self.profiles.addItems(config_mod.list_profiles())
        index = self.profiles.findText(current)
        if index >= 0:
            self.profiles.setCurrentIndex(index)

    def _profile_selected(self, index: int) -> None:
        if index <= 0:
            return
        name = self.profiles.itemText(index)
        self.cfg = config_mod.load_profile(name)
        self.load_config_into_widgets()
        self._on_config_changed()
        self.statusBar().showMessage(f"Profilo «{name}» caricato", 4000)

    def _save_profile(self) -> None:
        name, ok = QInputDialog.getText(self, "Salva profilo", "Nome del profilo:")
        if not ok or not name.strip():
            return
        self.collect_widgets_into_config()
        config_mod.save_profile(self.cfg, name)
        self._reload_profiles()
        index = self.profiles.findText(name.strip())
        if index >= 0:
            self.profiles.setCurrentIndex(index)
        self.statusBar().showMessage(f"Profilo «{name}» salvato", 4000)

    # -- avvio e arresto ---------------------------------------------------

    def _is_running(self) -> bool:
        return self.pipeline is not None and self.pipeline.is_running()

    def start_chain(self) -> None:
        self.collect_widgets_into_config()
        self.cfg.save()

        self.pipeline = Pipeline(
            self.cfg,
            on_log=lambda key, line: self.log_line.emit(key, line),
            on_state=lambda key, state: self.stage_state.emit(key, state),
        )

        self._build_status_lights()
        self.statusBar().showMessage("Avvio in corso...")
        self.start_button.setEnabled(False)

        problems = self.pipeline.start()
        if problems:
            self.start_button.setEnabled(True)
            self.statusBar().showMessage("Avvio non riuscito")
            QMessageBox.warning(
                self, "Impossibile avviare",
                "La catena non è stata avviata:\n\n"
                + "\n".join(f"• {p}" for p in problems),
            )
            return

        self._pending_restart = False
        self.stop_button.setEnabled(True)
        self.apply_button.setEnabled(True)
        self.statusBar().showMessage("Catena in esecuzione")
        self.tabs.setCurrentWidget(self.log_view)
        self._refresh_banner()

    def stop_chain(self) -> None:
        if self.pipeline is None:
            return
        self.statusBar().showMessage("Arresto in corso...")
        self.stop_button.setEnabled(False)
        self.pipeline.stop()
        self.apply_button.setEnabled(False)
        self._pending_restart = False
        self.statusBar().showMessage("Catena fermata")
        self._refresh_banner()

    def apply_hot(self) -> None:
        if self.pipeline is None or not self._is_running():
            return
        self.collect_widgets_into_config()
        control = self.pipeline.receiver()
        if control.apply_config(self.cfg):
            self.statusBar().showMessage("Parametri applicati al ricevitore", 4000)
            self._pending_restart = False
        else:
            self.statusBar().showMessage(
                "Il ricevitore non ha accettato tutti i parametri", 6000)
        self._refresh_banner()

    def _build_status_lights(self) -> None:
        while self.status_row.count():
            item = self.status_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._lights.clear()

        for stage in self.pipeline.build_stages():
            light = StatusLight(stage.label)
            self._lights[stage.key] = light
            self.status_row.addWidget(light)
            self.log_view.register_stage(stage.key, stage.label)
        self.status_row.addStretch(1)

    # -- aggiornamenti periodici -------------------------------------------

    def _poll(self) -> None:
        if self.pipeline is None:
            return
        self.pipeline.poll()
        for stage in self.pipeline.stages:
            light = self._lights.get(stage.key)
            if light:
                light.set_state(stage.state)

        if self.stop_button.isEnabled() and not self.pipeline.is_running():
            self.stop_button.setEnabled(False)
            self.apply_button.setEnabled(False)
            self.statusBar().showMessage("Tutti gli stadi sono terminati")
            self._refresh_banner()

    def _poll_receiver(self) -> None:
        """Rilegge i parametri dal ricevitore.

        Con il controllo XMLRPC attivo, telive può cambiare frequenza, ppm e
        guadagno per conto suo (sintonia automatica, scansione, correzione
        AFC): mostrare i valori reali evita di far credere all'utente che
        comandi solo lui.
        """
        if not self._is_running() or not self.cfg.telive.xmlrpc_enabled:
            return
        status = self.pipeline.receiver().status()
        if not status.reachable:
            return
        self.statusBar().showMessage(
            f"Ricevitore: {status.freq_hz / 1e6:.4f} MHz · "
            f"guadagno {status.gain:.0f} dB · {status.ppm:+.2f} ppm"
        )

    # -- azioni varie ------------------------------------------------------

    def _on_log_line(self, key: str, line: str) -> None:
        self.log_view.append(key, line)

    def _on_stage_state(self, key: str, state: StageState) -> None:
        light = self._lights.get(key)
        if light:
            light.set_state(state)
        if state is StageState.FAILED:
            stage = self.pipeline.stage(key) if self.pipeline else None
            label = stage.label if stage else key
            self.statusBar().showMessage(f"Stadio in errore: {label}")

    def _show_cmdline(self) -> None:
        self.collect_widgets_into_config()
        pipeline = self.pipeline or Pipeline(self.cfg)
        blocks = []
        for i, stage in enumerate(pipeline.build_stages(), start=1):
            lines = [f"# {i}. {stage.label}"]
            if stage.cwd:
                lines.append(f"cd {stage.cwd}")
            lines += [f"export {k}={v}" for k, v in sorted(stage.env.items())]
            lines.append(stage.cmdline)
            blocks.append("\n".join(lines))

        dialog = QMessageBox(self)
        dialog.setWindowTitle("Comandi equivalenti")
        dialog.setText(
            "Questi sono i comandi che l'applicazione esegue al posto tuo, "
            "nell'ordine di avvio:"
        )
        dialog.setDetailedText("\n\n".join(blocks))
        dialog.exec_()

    def _run_installer(self, which: str) -> None:
        script = {"codec": "40_install_codec.sh", "apt": "10_apt_deps.sh"}[which]
        path = paths.scripts_dir() / script
        if not path.is_file():
            QMessageBox.warning(
                self, "Script non trovato",
                f"{path} non esiste.\nReinstalla l'applicazione con ./install.sh.")
            return

        terminal, _ = deps.find_terminal()
        if not terminal:
            QMessageBox.information(
                self, "Nessun terminale",
                f"Esegui questo comando in un terminale:\n\n"
                f"PREFIX={paths.prefix()} {path}")
            return

        env = {"PREFIX": str(paths.prefix())}
        try:
            subprocess.Popen(
                [terminal, "-e", str(path)],
                env={**env, **_os_environ()},
                start_new_session=True,
            )
        except OSError as exc:
            QMessageBox.warning(self, "Avvio non riuscito", str(exc))
            return
        self.statusBar().showMessage(
            "Installazione avviata in un terminale separato; al termine premi "
            "«Ricontrolla».", 8000)

    def _about(self) -> None:
        from .. import __version__
        QMessageBox.about(
            self, "OsmoTetra",
            f"<h3>OsmoTetraUbuntu {__version__}</h3>"
            "<p>Installazione, avvio automatico e configurazione grafica della "
            "suite di monitoraggio TETRA di Jacek Lipkowski SQ5BPF.</p>"
            "<p>Decoder e interfaccia sono opera di SQ5BPF "
            "(<i>osmo-tetra-sq5bpf</i>, <i>telive</i>) e, per osmo-tetra, di "
            "Harald Welte e del progetto Osmocom.</p>"
            "<p>Licenza GPL-3.0.</p>"
            "<p><b>La ricezione di traffico TETRA è regolata in modo diverso "
            "da paese a paese: verifica di essere autorizzato.</b></p>"
        )

    # -- chiusura ----------------------------------------------------------

    def closeEvent(self, event):  # noqa: N802 (nome imposto da Qt)
        if self._is_running():
            answer = QMessageBox.question(
                self, "Uscire?",
                "La catena è in esecuzione. Fermarla e uscire?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self.stop_chain()
        self.collect_widgets_into_config()
        self.cfg.save()
        event.accept()


def _scrollable(widget: QWidget) -> QScrollArea:
    """Racchiude una scheda in un'area scorrevole verticale."""
    area = QScrollArea()
    area.setWidget(widget)
    area.setWidgetResizable(True)
    area.setFrameShape(QScrollArea.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    return area


def _os_environ() -> dict:
    import os
    return dict(os.environ)
