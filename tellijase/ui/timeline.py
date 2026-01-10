"""Timeline widget for FRAME mode - tracker-style sequencer."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QGroupBox,
)


class FrameCell(QWidget):
    """Single cell in the timeline representing one frame of data."""

    clicked = Signal(int, int)  # (track_index, frame_number)

    def __init__(
        self,
        track_index: int,
        frame_number: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.track_index = track_index
        self.frame_number = frame_number
        self.is_filled = False
        self.setFixedSize(40, 24)
        self.setStyleSheet("FrameCell { border: 1px solid #555; background-color: #2a2a2a; }")

    def set_filled(self, filled: bool) -> None:
        """Mark this cell as filled (has event data)."""
        self.is_filled = filled
        if filled:
            self.setStyleSheet(
                "FrameCell { border: 1px solid #00aaff; " "background-color: #004466; }"
            )
        else:
            self.setStyleSheet("FrameCell { border: 1px solid #555; background-color: #2a2a2a; }")

    def mousePressEvent(self, event) -> None:
        """Handle click on this cell."""
        self.clicked.emit(self.track_index, self.frame_number)
        super().mousePressEvent(event)


class TrackTimeline(QWidget):
    """Timeline for a single track (channel or noise)."""

    frame_clicked = Signal(int, int)  # (track_index, frame_number)

    def __init__(
        self,
        track_index: int,
        track_name: str,
        num_frames: int = 128,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.track_index = track_index
        self.track_name = track_name
        self.num_frames = num_frames
        self.cells: list[FrameCell] = []

        layout = QHBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Track label (fixed width)
        label = QLabel(track_name)
        label.setFixedWidth(80)
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        label.setStyleSheet("font-weight: bold; padding-right: 8px;")
        layout.addWidget(label)

        # Frame cells (scrollable)
        cells_container = QWidget()
        cells_layout = QHBoxLayout(cells_container)
        cells_layout.setSpacing(0)
        cells_layout.setContentsMargins(0, 0, 0, 0)

        for frame_num in range(num_frames):
            cell = FrameCell(track_index, frame_num)
            cell.clicked.connect(self.frame_clicked)
            cells_layout.addWidget(cell)
            self.cells.append(cell)

        cells_layout.addStretch()
        layout.addWidget(cells_container)

    def set_frame_filled(self, frame_number: int, filled: bool) -> None:
        """Mark a specific frame as filled or empty."""
        if 0 <= frame_number < len(self.cells):
            self.cells[frame_number].set_filled(filled)


class FrameTimeline(QWidget):
    """Complete timeline view with all tracks."""

    frame_clicked = Signal(int, int)  # (track_index, frame_number)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.num_frames = 128
        self.tracks: list[TrackTimeline] = []

        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header with frame numbers
        header_row = QHBoxLayout()
        header_label = QLabel("")
        header_label.setFixedWidth(80)  # Match track label width
        header_row.addWidget(header_label)

        # Frame number markers (every 16 frames)
        frame_markers = QWidget()
        frame_markers_layout = QHBoxLayout(frame_markers)
        frame_markers_layout.setSpacing(0)
        frame_markers_layout.setContentsMargins(0, 0, 0, 0)

        for i in range(0, self.num_frames, 16):
            marker = QLabel(f"{i}")
            marker.setFixedWidth(40 * 16)  # Span 16 cells
            marker.setStyleSheet("color: #888; font-size: 9px;")
            frame_markers_layout.addWidget(marker)

        frame_markers_layout.addStretch()
        header_row.addWidget(frame_markers)
        layout.addLayout(header_row)

        # Create track timelines
        track_names = ["Channel A", "Channel B", "Channel C", "Noise", "Envelope"]
        for idx, name in enumerate(track_names):
            track = TrackTimeline(idx, name, self.num_frames)
            track.frame_clicked.connect(self.frame_clicked)
            layout.addWidget(track)
            self.tracks.append(track)

    def set_frame_data(self, track_index: int, frame_number: int, filled: bool) -> None:
        """Set whether a frame has data or not."""
        if 0 <= track_index < len(self.tracks):
            self.tracks[track_index].set_frame_filled(frame_number, filled)


class FrameEditor(QGroupBox):
    """Editor for a single frame's parameters."""

    frame_applied = Signal(int, int, dict)  # (track_index, frame_number, data)
    frame_cleared = Signal(int, int)  # (track_index, frame_number)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Frame Editor", parent)
        self.current_track = -1
        self.current_frame = -1

        layout = QVBoxLayout(self)

        self.info_label = QLabel("Click a frame cell to edit")
        self.info_label.setStyleSheet("color: #888;")
        layout.addWidget(self.info_label)

        # Frequency control
        freq_row = QHBoxLayout()
        freq_row.addWidget(QLabel("Frequency (Hz):"))
        self.freq_spin = QSpinBox()
        self.freq_spin.setRange(27, 2000)
        self.freq_spin.setValue(440)
        self.freq_spin.setEnabled(False)
        freq_row.addWidget(self.freq_spin)
        freq_row.addStretch()
        layout.addLayout(freq_row)

        # Volume control
        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("Volume (0-15):"))
        self.vol_spin = QSpinBox()
        self.vol_spin.setRange(0, 15)
        self.vol_spin.setValue(10)
        self.vol_spin.setEnabled(False)
        vol_row.addWidget(self.vol_spin)
        vol_row.addStretch()
        layout.addLayout(vol_row)

        # Tone/Noise enables
        enables_row = QHBoxLayout()
        self.btn_tone_enable = QPushButton("Tone Enabled")
        self.btn_tone_enable.setCheckable(True)
        self.btn_tone_enable.setChecked(True)
        self.btn_tone_enable.setEnabled(False)
        enables_row.addWidget(self.btn_tone_enable)

        self.btn_noise_enable = QPushButton("Noise Enabled")
        self.btn_noise_enable.setCheckable(True)
        self.btn_noise_enable.setChecked(False)
        self.btn_noise_enable.setEnabled(False)
        enables_row.addWidget(self.btn_noise_enable)

        enables_row.addStretch()
        layout.addLayout(enables_row)

        # Apply/Clear buttons
        button_row = QHBoxLayout()
        self.btn_apply = QPushButton("Apply to Frame")
        self.btn_apply.setEnabled(False)
        button_row.addWidget(self.btn_apply)

        self.btn_clear = QPushButton("Clear Frame")
        self.btn_clear.setEnabled(False)
        button_row.addWidget(self.btn_clear)

        button_row.addStretch()
        layout.addLayout(button_row)

        layout.addStretch()

        # Connect button signals
        self.btn_apply.clicked.connect(self._on_apply_clicked)
        self.btn_clear.clicked.connect(self._on_clear_clicked)

    def _on_apply_clicked(self) -> None:
        """Apply button clicked - emit frame data."""
        if self.current_track < 0 or self.current_frame < 0:
            return

        # Collect frame data from UI controls
        data = {
            "frequency": self.freq_spin.value() if self.freq_spin.isEnabled() else None,
            "volume": self.vol_spin.value(),
            "tone_enabled": self.btn_tone_enable.isChecked()
            if self.btn_tone_enable.isEnabled()
            else None,
            "noise_enabled": self.btn_noise_enable.isChecked()
            if self.btn_noise_enable.isEnabled()
            else None,
        }

        self.frame_applied.emit(self.current_track, self.current_frame, data)

    def _on_clear_clicked(self) -> None:
        """Clear button clicked - clear the frame."""
        if self.current_track < 0 or self.current_frame < 0:
            return

        self.frame_cleared.emit(self.current_track, self.current_frame)

    def set_frame(self, track_index: int, frame_number: int) -> None:
        """Set the currently edited frame."""
        self.current_track = track_index
        self.current_frame = frame_number

        track_names = ["Channel A", "Channel B", "Channel C", "Noise", "Envelope"]
        track_name = track_names[track_index] if track_index < len(track_names) else "Unknown"

        self.info_label.setText(f"Editing: {track_name} - Frame {frame_number}")
        self.freq_spin.setEnabled(track_index < 3)  # Only for tone channels
        self.vol_spin.setEnabled(True)
        self.btn_tone_enable.setEnabled(track_index < 3)
        self.btn_noise_enable.setEnabled(track_index < 3)
        self.btn_apply.setEnabled(True)
        self.btn_clear.setEnabled(True)

    def load_frame_data(self, data: dict | None) -> None:
        """Load frame data into the editor controls.

        Args:
            data: Frame data dict with frequency, volume, tone_enabled, noise_enabled
                  or None for empty frame (resets to defaults)
        """
        if data is None:
            # Reset to defaults for empty frame
            self.freq_spin.setValue(440)
            self.vol_spin.setValue(10)
            self.btn_tone_enable.setChecked(True)
            self.btn_noise_enable.setChecked(False)
        else:
            # Load data from frame
            if data.get("frequency") is not None:
                self.freq_spin.setValue(int(data["frequency"]))
            if data.get("volume") is not None:
                self.vol_spin.setValue(int(data["volume"]))
            if data.get("tone_enabled") is not None:
                self.btn_tone_enable.setChecked(bool(data["tone_enabled"]))
            if data.get("noise_enabled") is not None:
                self.btn_noise_enable.setChecked(bool(data["noise_enabled"]))


__all__ = ["FrameTimeline", "FrameEditor"]
