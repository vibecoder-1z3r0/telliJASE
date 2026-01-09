"""Widgets for JAM mode channel controls."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class ChannelControl(QGroupBox):
    """UI for one PSG channel - emits high-level signals.

    Signals emit domain concepts (frequency in Hz, volume 0-15, mixer enables)
    rather than low-level register values.
    """

    # High-level signals (domain model, not hardware registers)
    frequency_changed = Signal(float)
    volume_changed = Signal(int)
    tone_enabled_changed = Signal(bool)
    noise_enabled_changed = Signal(bool)

    def __init__(self, channel_index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.channel_index = channel_index
        channel_name = chr(ord("A") + channel_index)
        self.setTitle(f"Channel {channel_name}")

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Frequency slider (27 Hz - 2000 Hz, hardware min to usable musical range)
        # Default to power chord: A2 (110), A3 (220), E4 (330)
        power_chord_freqs = [110, 220, 330]
        initial_freq = power_chord_freqs[channel_index]
        self.freq_label = QLabel(f"Frequency: {initial_freq} Hz")
        layout.addWidget(self.freq_label)

        # Horizontal layout with slider and text input
        freq_row = QHBoxLayout()
        self.freq_slider = QSlider(Qt.Horizontal)
        self.freq_slider.setRange(27, 2000)  # Hardware minimum (period=4095) to musical range
        self.freq_slider.setValue(initial_freq)
        self.freq_slider.valueChanged.connect(self._on_freq_slider_changed)

        self.freq_input = QLineEdit()
        self.freq_input.setMaximumWidth(70)
        self.freq_input.setText(str(initial_freq))
        self.freq_input.editingFinished.connect(self._on_freq_input_changed)

        freq_row.addWidget(self.freq_slider)
        freq_row.addWidget(self.freq_input)
        layout.addLayout(freq_row)

        # Volume slider (0-15)
        self.vol_label = QLabel("Volume: 4")
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 15)
        self.vol_slider.setValue(4)
        self.vol_slider.valueChanged.connect(self._on_vol_changed)
        layout.addWidget(self.vol_label)
        layout.addWidget(self.vol_slider)

        # Mixer checkboxes (R7 control)
        self.tone_check = QCheckBox("Tone")
        self.tone_check.setChecked(True)
        self.tone_check.toggled.connect(self.tone_enabled_changed)
        layout.addWidget(self.tone_check)

        self.noise_check = QCheckBox("Noise")
        self.noise_check.setChecked(False)
        self.noise_check.toggled.connect(self.noise_enabled_changed)
        layout.addWidget(self.noise_check)

        layout.addStretch()

    def _on_freq_slider_changed(self, value: int) -> None:
        """Frequency slider moved - update text input and emit signal."""
        self.freq_label.setText(f"Frequency: {value} Hz")
        self.freq_input.blockSignals(True)
        self.freq_input.setText(str(value))
        self.freq_input.blockSignals(False)
        self.frequency_changed.emit(float(value))

    def _on_freq_input_changed(self) -> None:
        """Frequency text input changed - update slider and emit signal."""
        try:
            value = int(self.freq_input.text())
            # Clamp to slider range
            value = max(self.freq_slider.minimum(), min(self.freq_slider.maximum(), value))
            self.freq_slider.blockSignals(True)
            self.freq_slider.setValue(value)
            self.freq_slider.blockSignals(False)
            self.freq_label.setText(f"Frequency: {value} Hz")
            self.freq_input.setText(str(value))  # Show clamped value
            self.frequency_changed.emit(float(value))
        except ValueError:
            # Invalid input - restore from slider
            self.freq_input.setText(str(self.freq_slider.value()))

    def _on_vol_changed(self, value: int) -> None:
        """Volume slider moved - emit high-level signal."""
        self.vol_label.setText(f"Volume: {value}")
        self.volume_changed.emit(value)

    def set_state(self, frequency: float, volume: int, tone_enabled: bool, noise_enabled: bool) -> None:
        """Update UI from model (for loading projects).

        Args:
            frequency: Frequency in Hz
            volume: Volume 0-15
            tone_enabled: Tone mixer enable
            noise_enabled: Noise mixer enable
        """
        # Block signals to avoid feedback loop
        self.freq_slider.blockSignals(True)
        self.freq_input.blockSignals(True)
        self.vol_slider.blockSignals(True)
        self.tone_check.blockSignals(True)
        self.noise_check.blockSignals(True)

        self.freq_slider.setValue(int(frequency))
        self.freq_input.setText(str(int(frequency)))
        self.vol_slider.setValue(volume)
        self.tone_check.setChecked(tone_enabled)
        self.noise_check.setChecked(noise_enabled)

        self.freq_slider.blockSignals(False)
        self.freq_input.blockSignals(False)
        self.vol_slider.blockSignals(False)
        self.tone_check.blockSignals(False)
        self.noise_check.blockSignals(False)

        # Update labels
        self.freq_label.setText(f"Frequency: {int(frequency)} Hz")
        self._on_vol_changed(volume)

    def emit_state(self) -> None:
        """Force emission of current UI state (for initialization)."""
        self.frequency_changed.emit(float(self.freq_slider.value()))
        self.volume_changed.emit(self.vol_slider.value())
        self.tone_enabled_changed.emit(self.tone_check.isChecked())
        self.noise_enabled_changed.emit(self.noise_check.isChecked())


__all__ = ["ChannelControl"]
