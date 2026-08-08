"""Vista dei log degli stadi.

Il decoder è molto verboso (una riga per burst): la vista tiene un numero
limitato di righe e permette di filtrare per stadio.

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import re
from collections import deque

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

#: Righe conservate in memoria, su tutti gli stadi.
MAX_LINES = 5000

#: telive disegna un'interfaccia ncurses: se il suo output finisce nel log,
#: le sequenze di escape lo rendono illeggibile.
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b[()][A-Z0-9]|[\x00-\x08\x0b-\x1f\x7f]")


def strip_ansi(text: str) -> str:
    return _ANSI.sub("", text)


class LogView(QWidget):
    """Log unificato con filtro per stadio."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lines: deque[tuple[str, str]] = deque(maxlen=MAX_LINES)
        self._filter = ""

        self.stage_filter = QComboBox()
        self.stage_filter.addItem("Tutti gli stadi", "")
        self.stage_filter.currentIndexChanged.connect(self._refilter)

        self.autoscroll = QCheckBox("Scorri automaticamente")
        self.autoscroll.setChecked(True)

        clear_button = QPushButton("Svuota")
        clear_button.clicked.connect(self.clear)

        save_button = QPushButton("Salva su file...")
        save_button.clicked.connect(self._save)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(MAX_LINES)
        self.text.setLineWrapMode(QPlainTextEdit.NoWrap)
        font = QFont("Monospace")
        font.setStyleHint(QFont.TypeWriter)
        font.setPointSize(9)
        self.text.setFont(font)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Mostra:"))
        toolbar.addWidget(self.stage_filter)
        toolbar.addStretch(1)
        toolbar.addWidget(self.autoscroll)
        toolbar.addWidget(clear_button)
        toolbar.addWidget(save_button)

        layout = QVBoxLayout(self)
        layout.addLayout(toolbar)
        layout.addWidget(self.text, 1)

    # -- API ---------------------------------------------------------------

    def register_stage(self, key: str, label: str) -> None:
        if self.stage_filter.findData(key) < 0:
            self.stage_filter.addItem(label, key)

    def append(self, stage_key: str, line: str) -> None:
        clean = strip_ansi(line).rstrip()
        if not clean:
            return
        self._lines.append((stage_key, clean))
        if not self._filter or self._filter == stage_key:
            self._append_to_view(stage_key, clean)

    def clear(self) -> None:
        self._lines.clear()
        self.text.clear()

    def contents(self) -> str:
        return "\n".join(f"[{key}] {line}" for key, line in self._lines)

    # -- interni -----------------------------------------------------------

    def _append_to_view(self, stage_key: str, line: str) -> None:
        scrollbar = self.text.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum() - 4
        self.text.appendPlainText(f"[{stage_key}] {line}")
        if self.autoscroll.isChecked() and at_bottom:
            scrollbar.setValue(scrollbar.maximum())

    def _refilter(self) -> None:
        self._filter = self.stage_filter.currentData() or ""
        self.text.clear()
        for key, line in self._lines:
            if not self._filter or self._filter == key:
                self.text.appendPlainText(f"[{key}] {line}")

    def _save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Salva il log", "osmotetra.log", "File di testo (*.log *.txt)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(self.contents() + "\n")
        except OSError as exc:
            QMessageBox.warning(self, "Salvataggio non riuscito", str(exc))
