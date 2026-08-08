"""Widget riutilizzabili dell'interfaccia.

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import (
    QDoubleSpinBox, QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget,
)

from ..pipeline import StageState

#: Colori degli indicatori di stato, scelti per restare distinguibili anche
#: da chi non percepisce bene il rosso e il verde (la forma del testo
#: accanto all'indicatore resta comunque la fonte primaria).
_STATE_COLORS = {
    StageState.STOPPED: QColor("#9aa0a6"),
    StageState.STARTING: QColor("#e8a33d"),
    StageState.RUNNING: QColor("#2e9e5b"),
    StageState.FAILED: QColor("#cc3d3d"),
}


class StatusLight(QWidget):
    """Pallino colorato con etichetta, per lo stato di uno stadio."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self._state = StageState.STOPPED
        self._dot = _Dot(self)
        self._label = QLabel(label)
        self._label.setToolTip("Stato: fermo")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 12, 0)
        layout.setSpacing(6)
        layout.addWidget(self._dot)
        layout.addWidget(self._label)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

    def set_state(self, state: StageState) -> None:
        self._state = state
        self._dot.set_color(_STATE_COLORS.get(state, _STATE_COLORS[StageState.STOPPED]))
        self._label.setToolTip(f"Stato: {state.value}")

    @property
    def state(self) -> StageState:
        return self._state


class _Dot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = _STATE_COLORS[StageState.STOPPED]
        self.setFixedSize(12, 12)

    def set_color(self, color: QColor) -> None:
        self._color = color
        self.update()

    def paintEvent(self, event):  # noqa: N802 (nome imposto da Qt)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(self._color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(1, 1, 10, 10)


class MHzSpinBox(QDoubleSpinBox):
    """Frequenza in MHz, con conversione da e verso gli Hz.

    Le frequenze TETRA si scrivono naturalmente in MHz con tre o quattro
    decimali (391.1125), mentre tutta la catena lavora in Hz.
    """

    def __init__(self, parent=None, minimum=0.0, maximum=6000.0, decimals=6):
        super().__init__(parent)
        self.setDecimals(decimals)
        self.setRange(minimum, maximum)
        self.setSingleStep(0.0125)   # passo di canale TETRA
        self.setSuffix(" MHz")
        self.setKeyboardTracking(False)

    def hz(self) -> float:
        return self.value() * 1e6

    def set_hz(self, value: float) -> None:
        self.setValue(float(value) / 1e6)


class KHzSpinBox(QDoubleSpinBox):
    """Offset in kHz, con conversione da e verso gli Hz."""

    def __init__(self, parent=None, limit_khz=5000.0):
        super().__init__(parent)
        self.setDecimals(4)
        self.setRange(-limit_khz, limit_khz)
        self.setSingleStep(12.5)
        self.setSuffix(" kHz")
        self.setKeyboardTracking(False)

    def hz(self) -> float:
        return self.value() * 1e3

    def set_hz(self, value: float) -> None:
        self.setValue(float(value) / 1e3)


def separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.VLine)
    line.setFrameShadow(QFrame.Sunken)
    return line


def hint(text: str) -> QLabel:
    """Testo esplicativo sotto un gruppo di campi."""
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color: palette(mid);")
    return label
