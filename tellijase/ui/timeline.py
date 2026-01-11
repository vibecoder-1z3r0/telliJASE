"""Timeline widget for FRAME mode - sparse keyframe sequencer with inline editing."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QPainter, QColor, QPen, QMouseEvent
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QGroupBox,
    QGridLayout,
)


# Constants for layout
CELL_WIDTH = 100  # Width of each keyframe cell
CELL_HEIGHT = 95  # Height of each keyframe cell
TRACK_HEIGHT = 120  # Height of each track row (includes cell + padding)


class FrameCell(QWidget):
    """Single keyframe cell with inline editing widgets."""

    data_changed = Signal(int, int, dict)  # (track_index, frame_number, data)
    clicked = Signal(int, int)  # (track_index, frame_number)
    delete_requested = Signal(int, int)  # (track_index, frame_number)

    def __init__(
        self,
        track_index: int,
        frame_number: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.track_index = track_index
        self.frame_number = frame_number
        self.is_highlighted = False  # Playback position highlight
        self.is_selected = False  # Selection state
        self.frame_data = None

        self.setFixedSize(CELL_WIDTH, CELL_HEIGHT)
        self.setFocusPolicy(Qt.StrongFocus)

        # Main layout
        layout = QGridLayout(self)
        layout.setSpacing(1)
        layout.setContentsMargins(2, 2, 2, 2)

        # Row 1: [Frequency/Period] Hz/Per label
        self.freq_spin = QSpinBox()
        if track_index == 3:  # Noise channel - use period
            self.freq_spin.setRange(0, 31)
            self.freq_spin.setValue(1)
            freq_label = QLabel("Per")
        else:  # Tone channels (A, B, C) or Envelope
            self.freq_spin.setRange(27, 2000)
            self.freq_spin.setValue(440)
            freq_label = QLabel("Hz")
        self.freq_spin.setFixedWidth(55)
        self.freq_spin.valueChanged.connect(self._on_data_changed)
        freq_label.setStyleSheet("color: #ccc; font-size: 8px;")
        layout.addWidget(self.freq_spin, 0, 0, 1, 2)
        layout.addWidget(freq_label, 0, 2)

        # Row 2: V [Volume] [Deactivate]
        v_label = QLabel("V")
        v_label.setStyleSheet("color: #ccc; font-size: 8px;")
        self.vol_spin = QSpinBox()
        self.vol_spin.setRange(0, 15)
        self.vol_spin.setValue(0)
        self.vol_spin.setFixedWidth(35)
        self.vol_spin.valueChanged.connect(self._on_data_changed)

        self.btn_deactivate = QPushButton("D")
        self.btn_deactivate.setCheckable(True)
        self.btn_deactivate.setFixedSize(22, 18)
        self.btn_deactivate.toggled.connect(self._on_deactivate_toggled)

        layout.addWidget(v_label, 1, 0)
        layout.addWidget(self.vol_spin, 1, 1)
        layout.addWidget(self.btn_deactivate, 1, 2)

        # Row 3: [Tone] [Noise] - only for tone channels
        self.btn_tone = QPushButton("T")
        self.btn_tone.setCheckable(True)
        self.btn_tone.setChecked(True)
        self.btn_tone.setFixedSize(30, 18)
        self.btn_tone.toggled.connect(self._on_tone_toggled)

        self.btn_noise = QPushButton("N")
        self.btn_noise.setCheckable(True)
        self.btn_noise.setChecked(False)
        self.btn_noise.setFixedSize(30, 18)
        self.btn_noise.toggled.connect(self._on_noise_toggled)

        if track_index < 3:  # Only show for tone channels
            layout.addWidget(self.btn_tone, 2, 0, 1, 2)
            layout.addWidget(self.btn_noise, 2, 2)
        else:
            self.btn_tone.setVisible(False)
            self.btn_noise.setVisible(False)

        # Row 4: Dur [duration]
        dur_label = QLabel("Dur")
        dur_label.setStyleSheet("color: #ccc; font-size: 8px;")
        self.dur_spin = QSpinBox()
        self.dur_spin.setRange(1, 300)
        self.dur_spin.setValue(1)
        self.dur_spin.setFixedWidth(35)
        self.dur_spin.valueChanged.connect(self._on_data_changed)

        layout.addWidget(dur_label, 3, 0)
        layout.addWidget(self.dur_spin, 3, 1, 1, 2)

    def _on_data_changed(self) -> None:
        """Emit signal when data changes."""
        self._emit_current_data()

    def _on_tone_toggled(self, checked: bool) -> None:
        """Update tone button styling and emit data."""
        self._update_button_style(self.btn_tone, checked, QColor(0, 255, 100))
        self._on_data_changed()

    def _on_noise_toggled(self, checked: bool) -> None:
        """Update noise button styling and emit data."""
        self._update_button_style(self.btn_noise, checked, QColor(0, 255, 100))
        self._on_data_changed()

    def _on_deactivate_toggled(self, checked: bool) -> None:
        """Update deactivate button styling and emit data."""
        self._update_button_style(self.btn_deactivate, checked, QColor(255, 100, 100))
        self._on_data_changed()

    def _update_button_style(
        self, button: QPushButton, checked: bool, active_color: QColor
    ) -> None:
        """Update button background color based on state."""
        if checked:
            button.setStyleSheet(
                f"background-color: rgb({active_color.red()}, {active_color.green()}, "
                f"{active_color.blue()}); color: black; font-weight: bold;"
            )
        else:
            button.setStyleSheet("background-color: #555; color: #aaa;")

    def _emit_current_data(self) -> None:
        """Collect and emit current frame data."""
        data = {
            "volume": self.vol_spin.value(),
            "deactivated": self.btn_deactivate.isChecked(),
            "duration": self.dur_spin.value(),
        }

        # Track-specific data
        if self.track_index < 3:  # Tone channels (A, B, C)
            data["frequency"] = self.freq_spin.value()
            data["tone_enabled"] = self.btn_tone.isChecked()
            data["noise_enabled"] = self.btn_noise.isChecked()
        elif self.track_index == 3:  # Noise channel
            data["period"] = self.freq_spin.value()
        elif self.track_index == 4:  # Envelope channel
            data["frequency"] = self.freq_spin.value()

        self.frame_data = data
        self.data_changed.emit(self.track_index, self.frame_number, data)

    def set_highlighted(self, highlighted: bool) -> None:
        """Set playback position highlight."""
        self.is_highlighted = highlighted
        self.update()

    def set_selected(self, selected: bool) -> None:
        """Set selection state."""
        self.is_selected = selected
        self.update()

    def set_data(self, data: dict) -> None:
        """Set frame data and update widget values."""
        self.frame_data = data

        # Block signals while updating
        self.freq_spin.blockSignals(True)
        self.vol_spin.blockSignals(True)
        self.dur_spin.blockSignals(True)
        self.btn_tone.blockSignals(True)
        self.btn_noise.blockSignals(True)
        self.btn_deactivate.blockSignals(True)

        # Load data
        if self.track_index == 3:  # Noise channel uses period
            if data.get("period") is not None:
                self.freq_spin.setValue(int(data["period"]))
        else:  # Tone channels and envelope use frequency
            if data.get("frequency") is not None:
                self.freq_spin.setValue(int(data["frequency"]))

        if data.get("volume") is not None:
            self.vol_spin.setValue(int(data["volume"]))
        if data.get("duration") is not None:
            self.dur_spin.setValue(int(data["duration"]))
        if data.get("tone_enabled") is not None:
            self.btn_tone.setChecked(bool(data["tone_enabled"]))
        if data.get("noise_enabled") is not None:
            self.btn_noise.setChecked(bool(data["noise_enabled"]))
        if data.get("deactivated") is not None:
            self.btn_deactivate.setChecked(bool(data["deactivated"]))

        # Update button styles
        self._update_button_style(self.btn_tone, self.btn_tone.isChecked(), QColor(0, 255, 100))
        self._update_button_style(self.btn_noise, self.btn_noise.isChecked(), QColor(0, 255, 100))
        self._update_button_style(
            self.btn_deactivate, self.btn_deactivate.isChecked(), QColor(255, 100, 100)
        )

        # Unblock signals
        self.freq_spin.blockSignals(False)
        self.vol_spin.blockSignals(False)
        self.dur_spin.blockSignals(False)
        self.btn_tone.blockSignals(False)
        self.btn_noise.blockSignals(False)
        self.btn_deactivate.blockSignals(False)

        self.update()

    def paintEvent(self, event) -> None:
        """Paint cell border based on state."""
        super().paintEvent(event)
        painter = QPainter(self)

        # Draw border based on state
        if self.is_highlighted:
            painter.setPen(QPen(QColor(255, 255, 0), 3))  # Yellow for playback
        elif self.is_selected:
            painter.setPen(QPen(QColor(0, 255, 255), 2))  # Cyan for selection
        else:
            painter.setPen(QPen(QColor(0, 170, 255), 1))  # Blue for keyframe

        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def keyPressEvent(self, event) -> None:
        """Handle Delete key to remove this keyframe."""
        if event.key() == Qt.Key_Delete:
            self.delete_requested.emit(self.track_index, self.frame_number)
        else:
            super().keyPressEvent(event)


class TimelineRuler(QWidget):
    """Ruler header for the timeline."""

    def __init__(self, max_frames: int = 1800, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.max_frames = max_frames
        self.setMinimumHeight(30)
        self.setMinimumWidth(500)

    def paintEvent(self, event) -> None:
        """Draw ruler background."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(50, 50, 50))

        # Draw label
        painter.setPen(QColor(200, 200, 200))
        painter.drawText(10, 20, "Keyframes (sequential view)")


class TrackTimeline(QWidget):
    """Timeline for a single track with sparse keyframes."""

    keyframe_clicked = Signal(int, int)  # (track_index, frame_number)
    data_changed = Signal(int, int, dict)  # (track_index, frame_number, data)
    keyframe_added = Signal(int, int)  # (track_index, frame_number)
    keyframe_deleted = Signal(int, int)  # (track_index, frame_number)

    def __init__(
        self,
        track_index: int,
        track_name: str,
        max_frames: int = 1800,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.track_index = track_index
        self.track_name = track_name
        self.max_frames = max_frames
        self.keyframes: dict[int, FrameCell] = {}  # frame_number -> FrameCell

        self.setMinimumHeight(TRACK_HEIGHT)
        # Width will be determined by number of keyframes, not max frames
        self.setMinimumWidth(500)  # Minimum reasonable width

        # Track label overlay
        self.label = QLabel(track_name, self)
        self.label.setStyleSheet(
            "background-color: rgba(60, 60, 60, 200); color: white; "
            "font-weight: bold; padding: 4px 8px; border-radius: 3px;"
        )
        self.label.move(5, 5)
        self.label.adjustSize()

    def add_keyframe(self, frame_number: int, data: dict) -> None:
        """Add a keyframe at the specified frame position."""
        if frame_number in self.keyframes:
            # Update existing keyframe
            self.keyframes[frame_number].set_data(data)
        else:
            # Create new keyframe cell
            cell = FrameCell(self.track_index, frame_number, self)
            cell.set_data(data)
            cell.data_changed.connect(self.data_changed)
            cell.clicked.connect(self.keyframe_clicked)
            cell.delete_requested.connect(self._on_delete_requested)

            self.keyframes[frame_number] = cell
            self.keyframe_added.emit(self.track_index, frame_number)

            # Reposition all keyframes sequentially
            self._reposition_keyframes()

    def remove_keyframe(self, frame_number: int) -> None:
        """Remove a keyframe at the specified frame position."""
        if frame_number in self.keyframes:
            cell = self.keyframes[frame_number]
            cell.deleteLater()
            del self.keyframes[frame_number]
            self.keyframe_deleted.emit(self.track_index, frame_number)

            # Reposition remaining keyframes
            self._reposition_keyframes()

    def _reposition_keyframes(self) -> None:
        """Reposition all keyframes sequentially based on sorted frame numbers."""
        spacing = 4  # Pixels between keyframes
        sorted_frames = sorted(self.keyframes.keys())

        for index, frame_num in enumerate(sorted_frames):
            cell = self.keyframes[frame_num]
            x = index * (CELL_WIDTH + spacing)
            y = (TRACK_HEIGHT - CELL_HEIGHT) // 2  # Center vertically
            cell.move(x, y)
            cell.show()

    def set_keyframe_highlighted(self, frame_number: int, highlighted: bool) -> None:
        """Set highlight state for a keyframe."""
        if frame_number in self.keyframes:
            self.keyframes[frame_number].set_highlighted(highlighted)

    def clear_all_highlights(self) -> None:
        """Clear all playback highlights."""
        for cell in self.keyframes.values():
            cell.set_highlighted(False)

    def _on_delete_requested(self, track_index: int, frame_number: int) -> None:
        """Handle delete request from a keyframe cell."""
        self.remove_keyframe(frame_number)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle click on empty timeline - TODO: implement add keyframe dialog."""
        # Check if click is on empty space (not on a keyframe cell)
        for cell in self.keyframes.values():
            if cell.geometry().contains(event.pos()):
                # Click is on existing keyframe, let the cell handle it
                super().mousePressEvent(event)
                return

        # TODO: Click on empty space - could prompt for frame number
        # For now, do nothing - user can add via editor panel

        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        """Paint track background."""
        painter = QPainter(self)

        # Draw track background
        painter.fillRect(self.rect(), QColor(60, 60, 60))


class FrameTimeline(QWidget):
    """Complete timeline view with all tracks."""

    frame_clicked = Signal(int, int)  # (track_index, frame_number)
    data_changed = Signal(int, int, dict)  # (track_index, frame_number, data)

    def __init__(self, max_frames: int = 1800, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.max_frames = max_frames
        self.tracks: list[TrackTimeline] = []

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Timeline ruler
        self.ruler = TimelineRuler(max_frames)
        layout.addWidget(self.ruler)

        # Create track timelines
        track_names = ["Channel A", "Channel B", "Channel C", "Noise", "Envelope"]
        for idx, name in enumerate(track_names):
            track = TrackTimeline(idx, name, max_frames)
            track.keyframe_clicked.connect(self.frame_clicked)
            track.data_changed.connect(self.data_changed)
            layout.addWidget(track)
            self.tracks.append(track)

            # Add default keyframe at frame 0
            if idx < 3:  # Tone channels
                default_data = {
                    "frequency": 440,
                    "volume": 0,
                    "tone_enabled": True,
                    "noise_enabled": False,
                    "deactivated": False,
                    "duration": 1,
                }
            elif idx == 3:  # Noise channel
                default_data = {
                    "period": 1,
                    "volume": 0,
                    "deactivated": False,
                    "duration": 1,
                }
            else:  # Envelope channel
                default_data = {
                    "frequency": 440,
                    "volume": 0,
                    "deactivated": False,
                    "duration": 1,
                }
            track.add_keyframe(0, default_data)

    def set_frame_data(self, track_index: int, frame_number: int, data: dict | None) -> None:
        """Set frame data (add or update keyframe)."""
        if 0 <= track_index < len(self.tracks):
            if data is None:
                self.tracks[track_index].remove_keyframe(frame_number)
            else:
                self.tracks[track_index].add_keyframe(frame_number, data)

    def set_playback_position(self, frame_number: int) -> None:
        """Highlight keyframes at playback position."""
        for track in self.tracks:
            track.clear_all_highlights()
            if frame_number >= 0:
                track.set_keyframe_highlighted(frame_number, True)


class FrameEditor(QGroupBox):
    """Editor for a single frame's parameters."""

    frame_applied = Signal(int, int, dict)  # (track_index, frame_number, data)
    frame_cleared = Signal(int, int)  # (track_index, frame_number)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Frame Editor", parent)
        self.current_track = -1
        self.current_frame = -1

        layout = QVBoxLayout(self)

        self.info_label = QLabel("Click a keyframe to edit")
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
        self.vol_spin.setValue(0)
        self.vol_spin.setEnabled(False)
        vol_row.addWidget(self.vol_spin)
        vol_row.addStretch()
        layout.addLayout(vol_row)

        # Duration control
        dur_row = QHBoxLayout()
        dur_row.addWidget(QLabel("Duration (frames):"))
        self.dur_spin = QSpinBox()
        self.dur_spin.setRange(1, 300)
        self.dur_spin.setValue(1)
        self.dur_spin.setEnabled(False)
        dur_row.addWidget(self.dur_spin)
        dur_row.addStretch()
        layout.addLayout(dur_row)

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

        data = {
            "frequency": self.freq_spin.value() if self.freq_spin.isEnabled() else None,
            "volume": self.vol_spin.value(),
            "duration": self.dur_spin.value(),
            "tone_enabled": (
                self.btn_tone_enable.isChecked() if self.btn_tone_enable.isEnabled() else None
            ),
            "noise_enabled": (
                self.btn_noise_enable.isChecked() if self.btn_noise_enable.isEnabled() else None
            ),
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
        self.freq_spin.setEnabled(track_index < 3)
        self.vol_spin.setEnabled(True)
        self.dur_spin.setEnabled(True)
        self.btn_tone_enable.setEnabled(track_index < 3)
        self.btn_noise_enable.setEnabled(track_index < 3)
        self.btn_apply.setEnabled(True)
        self.btn_clear.setEnabled(True)

    def load_frame_data(self, data: dict | None) -> None:
        """Load frame data into the editor controls."""
        if data is None:
            self.freq_spin.setValue(440)
            self.vol_spin.setValue(0)
            self.dur_spin.setValue(1)
            self.btn_tone_enable.setChecked(True)
            self.btn_noise_enable.setChecked(False)
        else:
            if data.get("frequency") is not None:
                self.freq_spin.setValue(int(data["frequency"]))
            if data.get("volume") is not None:
                self.vol_spin.setValue(int(data["volume"]))
            if data.get("duration") is not None:
                self.dur_spin.setValue(int(data["duration"]))
            if data.get("tone_enabled") is not None:
                self.btn_tone_enable.setChecked(bool(data["tone_enabled"]))
            if data.get("noise_enabled") is not None:
                self.btn_noise_enable.setChecked(bool(data["noise_enabled"]))


__all__ = ["FrameTimeline", "FrameEditor"]
