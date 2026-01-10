"""Timeline widget for FRAME mode - tracker-style sequencer."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QPainter, QColor, QPen
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
        self.frame_data = None  # Store actual frame data for visualization
        self.is_highlighted = False  # Playback position highlight
        self.setFixedSize(70, 55)  # Larger size for text labels

    def set_highlighted(self, highlighted: bool) -> None:
        """Set playback position highlight."""
        self.is_highlighted = highlighted
        self.update()

    def set_data(self, data: dict | None) -> None:
        """Set frame data and update visualization.

        Args:
            data: Frame data dict with frequency, volume, tone_enabled, noise_enabled
                  or None for empty frame
        """
        self.frame_data = data
        self.is_filled = data is not None
        self.update()  # Trigger repaint

    def set_filled(self, filled: bool) -> None:
        """Mark this cell as filled (has event data) - for backward compatibility."""
        if not filled:
            self.frame_data = None
        self.is_filled = filled
        self.update()

    def paintEvent(self, event) -> None:
        """Paint the cell with visual representation of the data."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background
        if self.is_filled and self.frame_data:
            painter.fillRect(self.rect(), QColor(30, 30, 30))
        else:
            painter.fillRect(self.rect(), QColor(42, 42, 42))

        # Border (highlight playback position with bright border)
        if self.is_highlighted:
            painter.setPen(QPen(QColor(255, 255, 0), 3))  # Yellow highlight
        elif self.is_filled:
            painter.setPen(QPen(QColor(0, 170, 255), 1))
        else:
            painter.setPen(QPen(QColor(85, 85, 85), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        # Draw data visualization if filled
        if self.is_filled and self.frame_data:
            self._draw_data_visualization(painter)

    def _draw_data_visualization(self, painter: QPainter) -> None:
        """Draw text representation of frame data.

        Layout:
        Line 1: [freq] Hz
        Line 2: V [vol] [M]
        Line 3: [T] [N]
        """
        from PySide6.QtGui import QFont

        frequency = self.frame_data.get("frequency")
        volume = self.frame_data.get("volume", 0)
        tone_enabled = self.frame_data.get("tone_enabled", False)
        noise_enabled = self.frame_data.get("noise_enabled", False)

        # Set up small font for compact display
        font = QFont("Monospace", 7)
        painter.setFont(font)
        painter.setPen(QColor(220, 220, 220))  # Light gray text

        y_offset = 12  # Start position

        # Line 1: Frequency (only for tone channels)
        if frequency is not None:
            freq_text = f"{int(frequency)}Hz"
            painter.drawText(4, y_offset, freq_text)
            y_offset += 14

        # Line 2: Volume
        vol_text = f"V:{volume}"
        painter.drawText(4, y_offset, vol_text)
        y_offset += 14

        # Line 3: Tone/Noise indicators
        x_pos = 4
        if tone_enabled:
            painter.setPen(QColor(0, 255, 100))  # Green for tone
            painter.drawText(x_pos, y_offset, "T")
            x_pos += 16

        if noise_enabled:
            painter.setPen(QColor(255, 150, 0))  # Orange for noise
            painter.drawText(x_pos, y_offset, "N")

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
        num_frames: int = 1800,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.track_index = track_index
        self.track_name = track_name
        self.num_frames = num_frames
        self.cells: list[FrameCell] = []

        # Style the track with background and border
        self.setStyleSheet(
            "TrackTimeline { background-color: #333; border: 1px solid #555; "
            "border-radius: 3px; margin: 2px; }"
        )

        layout = QHBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(4, 4, 4, 4)

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

    def set_frame_data(self, frame_number: int, data: dict | None) -> None:
        """Set frame data with visualization.

        Args:
            frame_number: Frame index
            data: Frame data dict or None for empty
        """
        if 0 <= frame_number < len(self.cells):
            self.cells[frame_number].set_data(data)


class FrameTimeline(QWidget):
    """Complete timeline view with all tracks."""

    frame_clicked = Signal(int, int)  # (track_index, frame_number)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.num_frames = 1800  # 30 seconds at 60 FPS
        self.tracks: list[TrackTimeline] = []

        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header with frame numbers
        header_row = QHBoxLayout()
        header_label = QLabel("")
        header_label.setFixedWidth(80)  # Match track label width
        header_row.addWidget(header_label)

        # Frame number markers (every 60 frames = 1 second at 60 FPS)
        frame_markers = QWidget()
        frame_markers_layout = QHBoxLayout(frame_markers)
        frame_markers_layout.setSpacing(0)
        frame_markers_layout.setContentsMargins(0, 0, 0, 0)

        marker_interval = 60  # 1 second intervals
        cell_width = 70  # Must match FrameCell width
        for i in range(0, self.num_frames, marker_interval):
            # Show time in seconds
            seconds = i // 60
            marker = QLabel(f"{seconds}s")
            marker.setFixedWidth(cell_width * marker_interval)  # Span interval
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

    def set_frame_data(
        self, track_index: int, frame_number: int, data: dict | None | bool
    ) -> None:
        """Set frame data for visualization.

        Args:
            track_index: Track index (0-4)
            frame_number: Frame number (0-127)
            data: Frame data dict for visualization, None for empty,
                  or bool for backward compatibility (True=filled, False=empty)
        """
        if 0 <= track_index < len(self.tracks):
            # Handle backward compatibility with bool
            if isinstance(data, bool):
                self.tracks[track_index].set_frame_filled(frame_number, data)
            else:
                # Pass actual data for visualization
                self.tracks[track_index].set_frame_data(frame_number, data)

    def set_playback_position(self, frame_number: int) -> None:
        """Highlight a specific frame across all tracks for playback position.

        Args:
            frame_number: Frame number to highlight (0-127), or -1 to clear all
        """
        for track in self.tracks:
            for idx, cell in enumerate(track.cells):
                cell.set_highlighted(idx == frame_number)


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
