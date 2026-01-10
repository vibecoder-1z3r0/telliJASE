"""Widgets for JAM mode channel controls."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
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
    muted_changed = Signal(bool)

    def __init__(self, channel_index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.channel_index = channel_index
        channel_name = chr(ord("A") + channel_index)
        self.setTitle(f"Channel {channel_name}")

        # Two-pane layout: Left (frequency + checkboxes) | Right (volume fader)
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(12)

        # Default to power chord: A2 (110), A3 (220), E4 (330)
        power_chord_freqs = [110, 220, 330]
        initial_freq = power_chord_freqs[channel_index]

        # Store volume for mute/unmute
        self._stored_volume = 4

        # === LEFT PANE: Frequency + Mixer ===
        left_pane = QVBoxLayout()
        left_pane.setSpacing(8)

        # Frequency slider (27 Hz - 2000 Hz, hardware min to usable musical range)
        self.freq_label = QLabel(f"Freq: {initial_freq} Hz")
        left_pane.addWidget(self.freq_label)

        # Horizontal layout with slider and text input
        freq_row = QHBoxLayout()
        self.freq_slider = QSlider(Qt.Horizontal)
        self.freq_slider.setRange(27, 2000)  # Hardware minimum (period=4095) to musical range
        self.freq_slider.setValue(initial_freq)
        self.freq_slider.setTickPosition(QSlider.TicksBelow)
        self.freq_slider.setTickInterval(100)  # Tick marks every 100 Hz
        self.freq_slider.valueChanged.connect(self._on_freq_slider_changed)

        self.freq_input = QLineEdit()
        self.freq_input.setMaximumWidth(60)
        self.freq_input.setText(str(initial_freq))
        self.freq_input.editingFinished.connect(self._on_freq_input_changed)

        freq_row.addWidget(self.freq_slider)
        freq_row.addWidget(self.freq_input)
        left_pane.addLayout(freq_row)

        # Frequency scale labels below slider
        freq_labels_layout = QHBoxLayout()
        freq_labels_layout.setContentsMargins(0, 0, 60, 0)  # Match text input width offset

        # Calculate positions for labels at 100, 500, 1000, 1500 Hz
        slider_range = 2000 - 27  # Total range
        label_positions = [100, 500, 1000, 1500]

        # Add initial spacer to account for slider starting at 27 Hz
        initial_offset = (100 - 27) / slider_range
        freq_labels_layout.addStretch(int(initial_offset * 1000))

        for i, freq in enumerate(label_positions):
            label = QLabel(str(freq))
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("font-size: 9px; color: gray;")
            freq_labels_layout.addWidget(label)

            # Add stretch between labels
            if i < len(label_positions) - 1:
                next_freq = label_positions[i + 1]
                stretch = (next_freq - freq) / slider_range
                freq_labels_layout.addStretch(int(stretch * 1000))
            else:
                # Final stretch to end (1500 to 2000)
                final_stretch = (2000 - freq) / slider_range
                freq_labels_layout.addStretch(int(final_stretch * 1000))

        left_pane.addLayout(freq_labels_layout)

        # Mixer toggle buttons (R7 control) - green when active
        self.tone_check = QPushButton("Tone")
        self.tone_check.setCheckable(True)
        self.tone_check.setChecked(True)
        self.tone_check.setStyleSheet("""
            QPushButton {
                background-color: palette(button);
                border: 1px solid palette(mid);
                padding: 4px;
            }
            QPushButton:checked {
                background-color: #388e3c;
                color: white;
                border: 1px solid #2e7d32;
            }
            QPushButton:checked:hover {
                background-color: #4caf50;
            }
        """)
        self.tone_check.toggled.connect(self.tone_enabled_changed)
        left_pane.addWidget(self.tone_check)

        self.noise_check = QPushButton("Noise")
        self.noise_check.setCheckable(True)
        self.noise_check.setChecked(False)
        self.noise_check.setStyleSheet("""
            QPushButton {
                background-color: palette(button);
                border: 1px solid palette(mid);
                padding: 4px;
            }
            QPushButton:checked {
                background-color: #388e3c;
                color: white;
                border: 1px solid #2e7d32;
            }
            QPushButton:checked:hover {
                background-color: #4caf50;
            }
        """)
        self.noise_check.toggled.connect(self.noise_enabled_changed)
        left_pane.addWidget(self.noise_check)

        left_pane.addStretch()

        # === RIGHT PANE: Vertical Volume Fader ===
        right_pane = QVBoxLayout()
        right_pane.setSpacing(4)

        # Volume label
        self.vol_label = QLabel("Vol: 4")
        self.vol_label.setAlignment(Qt.AlignCenter)
        right_pane.addWidget(self.vol_label)

        # Vertical volume slider (0-15) - like a mixer fader
        self.vol_slider = QSlider(Qt.Vertical)
        self.vol_slider.setRange(0, 15)
        self.vol_slider.setValue(4)
        self.vol_slider.setMinimumHeight(100)
        self.vol_slider.setTickPosition(QSlider.TicksBothSides)
        self.vol_slider.setTickInterval(1)  # Show tick for each volume level (0-15)
        self.vol_slider.setPageStep(1)  # Click on track moves by 1 instead of default 10
        self.vol_slider.valueChanged.connect(self._on_vol_changed)
        right_pane.addWidget(self.vol_slider, alignment=Qt.AlignCenter)

        # Mute toggle button
        self.mute_btn = QPushButton("MUTE")
        self.mute_btn.setCheckable(True)
        self.mute_btn.setMaximumWidth(60)
        self.mute_btn.setStyleSheet("""
            QPushButton {
                background-color: palette(button);
                border: 1px solid palette(mid);
                padding: 4px;
            }
            QPushButton:checked {
                background-color: #d32f2f;
                color: white;
                border: 1px solid #b71c1c;
            }
            QPushButton:checked:hover {
                background-color: #f44336;
            }
        """)
        self.mute_btn.toggled.connect(self._on_mute_toggled)
        right_pane.addWidget(self.mute_btn, alignment=Qt.AlignCenter)

        # Add panes to main layout
        main_layout.addLayout(left_pane, stretch=3)
        main_layout.addLayout(right_pane, stretch=1)

    def _on_freq_slider_changed(self, value: int) -> None:
        """Frequency slider moved - update text input and emit signal."""
        self.freq_label.setText(f"Freq: {value} Hz")
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
            self.freq_label.setText(f"Freq: {value} Hz")
            self.freq_input.setText(str(value))  # Show clamped value
            self.frequency_changed.emit(float(value))
        except ValueError:
            # Invalid input - restore from slider
            self.freq_input.setText(str(self.freq_slider.value()))

    def _on_vol_changed(self, value: int) -> None:
        """Volume slider moved - emit high-level signal."""
        self.vol_label.setText(f"Vol: {value}")
        # Store volume if not muted (for restoring after unmute)
        if not self.mute_btn.isChecked():
            self._stored_volume = value
        self.volume_changed.emit(value)

    def _on_mute_toggled(self, muted: bool) -> None:
        """Mute button toggled - set volume to 0 or restore previous."""
        if muted:
            # Store current volume and set to 0
            self._stored_volume = self.vol_slider.value()
            self.vol_slider.blockSignals(True)
            self.vol_slider.setValue(0)
            self.vol_slider.blockSignals(False)
            self.vol_label.setText("MUTED")
            self.vol_slider.setEnabled(False)
            self.volume_changed.emit(0)
        else:
            # Restore previous volume
            self.vol_slider.blockSignals(True)
            self.vol_slider.setValue(self._stored_volume)
            self.vol_slider.blockSignals(False)
            self.vol_label.setText(f"Vol: {self._stored_volume}")
            self.vol_slider.setEnabled(True)
            self.volume_changed.emit(self._stored_volume)

        self.muted_changed.emit(muted)

    def set_state(
        self,
        frequency: float,
        volume: int,
        tone_enabled: bool,
        noise_enabled: bool,
        muted: bool = False,
    ) -> None:
        """Update UI from model (for loading projects).

        Args:
            frequency: Frequency in Hz
            volume: Volume 0-15
            tone_enabled: Tone mixer enable
            noise_enabled: Noise mixer enable
            muted: Channel muted state
        """
        # Block signals to avoid feedback loop
        self.freq_slider.blockSignals(True)
        self.freq_input.blockSignals(True)
        self.vol_slider.blockSignals(True)
        self.tone_check.blockSignals(True)
        self.noise_check.blockSignals(True)
        self.mute_btn.blockSignals(True)

        self.freq_slider.setValue(int(frequency))
        self.freq_input.setText(str(int(frequency)))
        self.tone_check.setChecked(tone_enabled)
        self.noise_check.setChecked(noise_enabled)
        self.mute_btn.setChecked(muted)

        # Set volume and stored volume
        if muted:
            self._stored_volume = volume
            self.vol_slider.setValue(0)
            self.vol_slider.setEnabled(False)
            self.vol_label.setText("MUTED")
        else:
            self._stored_volume = volume
            self.vol_slider.setValue(volume)
            self.vol_slider.setEnabled(True)
            self.vol_label.setText(f"Vol: {volume}")

        self.freq_slider.blockSignals(False)
        self.freq_input.blockSignals(False)
        self.vol_slider.blockSignals(False)
        self.tone_check.blockSignals(False)
        self.noise_check.blockSignals(False)
        self.mute_btn.blockSignals(False)

        # Update frequency label
        self.freq_label.setText(f"Freq: {int(frequency)} Hz")

    def emit_state(self) -> None:
        """Force emission of current UI state (for initialization)."""
        self.frequency_changed.emit(float(self.freq_slider.value()))
        self.volume_changed.emit(self.vol_slider.value())
        self.tone_enabled_changed.emit(self.tone_check.isChecked())
        self.noise_enabled_changed.emit(self.noise_check.isChecked())
        self.muted_changed.emit(self.mute_btn.isChecked())


__all__ = ["ChannelControl"]
