"""Widgets for JAM mode channel controls."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QSlider, QVBoxLayout, QGroupBox

from tellijase.psg.utils import frequency_to_period

CHANNEL_REGS = [
    ("R0", "R1", "R8"),
    ("R2", "R3", "R9"),
    ("R4", "R5", "R10"),
]


class ChannelControl(QGroupBox):
    params_changed = Signal(dict)

    def __init__(self, channel_index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.channel_index = channel_index
        self.setTitle(f"Channel {chr(ord('A') + channel_index)}")
        self.freq_slider = QSlider()
        self.freq_slider.setOrientation(Qt.Horizontal)
        self.freq_slider.setRange(55, 2000)
        self.freq_slider.setValue(440 + channel_index * 110)
        self.freq_slider.valueChanged.connect(self._emit_changes)

        self.freq_label = QLabel()
        self._update_freq_label(self.freq_slider.value())
        self.freq_slider.valueChanged.connect(self._update_freq_label)

        self.volume_slider = QSlider()
        self.volume_slider.setOrientation(Qt.Horizontal)
        self.volume_slider.setRange(0, 15)
        self.volume_slider.setValue(12 - channel_index * 2)
        self.volume_slider.valueChanged.connect(self._emit_changes)

        self.volume_label = QLabel(f"Volume: {self.volume_slider.value()}")
        self.volume_slider.valueChanged.connect(lambda val: self.volume_label.setText(f"Volume: {val}"))

        layout = QVBoxLayout(self)
        layout.addWidget(self.freq_label)
        layout.addWidget(self.freq_slider)
        layout.addWidget(self.volume_label)
        layout.addWidget(self.volume_slider)
        layout.addStretch()

    def _emit_changes(self, _value: int) -> None:
        fine_reg, coarse_reg, vol_reg = CHANNEL_REGS[self.channel_index]
        freq = self.freq_slider.value()
        volume = self.volume_slider.value()
        period = frequency_to_period(freq)
        updates = {
            fine_reg: period & 0xFF,
            coarse_reg: (period >> 8) & 0x0F,
            vol_reg: volume,
        }
        self.params_changed.emit(updates)

    def _update_freq_label(self, value: int) -> None:
        self.freq_label.setText(f"Frequency: {value} Hz")

    def emit_state(self) -> None:
        """Force emission of the current slider state."""
        self._emit_changes(self.freq_slider.value())


__all__ = ["ChannelControl"]
