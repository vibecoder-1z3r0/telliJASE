"""Timeline widget for FRAME mode - card-based sequencer with inline editing."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QPen
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


class FrameCell(QWidget):
    """Single cell with inline editing widgets for frame data."""

    data_changed = Signal(int, int, dict)  # (track_index, frame_number, data)
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
        self.is_continuation = False  # True if showing continuation of previous frame
        self.is_highlighted = False  # Playback position highlight
        self.is_selected = False  # Selection state for copy/paste
        self.is_filled = False
        self.frame_data = None

        self.setFixedSize(100, 95)  # Reduced width from 120 to 100
        self.setFocusPolicy(Qt.StrongFocus)

        # Main layout
        layout = QGridLayout(self)
        layout.setSpacing(1)
        layout.setContentsMargins(2, 2, 2, 2)

        # Row 1: [Frequency/Period] Hz/label
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
        layout.addWidget(self.freq_spin, 0, 0, 1, 2)  # Span 2 columns
        layout.addWidget(freq_label, 0, 2)

        # Row 2: V [Volume] [Deactivate]
        v_label = QLabel("V")
        v_label.setStyleSheet("color: #ccc; font-size: 8px;")
        self.vol_spin = QSpinBox()
        self.vol_spin.setRange(0, 15)
        self.vol_spin.setValue(0)  # Default to silent
        self.vol_spin.setFixedWidth(35)
        self.vol_spin.valueChanged.connect(self._on_data_changed)

        self.btn_deactivate = QPushButton("D")
        self.btn_deactivate.setCheckable(True)
        self.btn_deactivate.setFixedSize(22, 18)
        self.btn_deactivate.toggled.connect(self._on_deactivate_toggled)

        layout.addWidget(v_label, 1, 0)
        layout.addWidget(self.vol_spin, 1, 1)
        layout.addWidget(self.btn_deactivate, 1, 2)

        # Row 3: [Tone] [Noise] - only for tone channels (A, B, C)
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

        # Only show Tone/Noise buttons for tone channels (A, B, C)
        if track_index < 3:
            layout.addWidget(self.btn_tone, 2, 0, 1, 2)  # Span 2 columns
            layout.addWidget(self.btn_noise, 2, 2)
        else:
            # Hide buttons for Noise and Envelope tracks
            self.btn_tone.setVisible(False)
            self.btn_noise.setVisible(False)

        # Row 4: Dur [duration]
        dur_label = QLabel("Dur")
        dur_label.setStyleSheet("color: #ccc; font-size: 8px;")
        self.dur_spin = QSpinBox()
        self.dur_spin.setRange(1, 300)  # 1-300 frames (up to 5 seconds at 60 FPS)
        self.dur_spin.setValue(1)
        self.dur_spin.setFixedWidth(35)
        self.dur_spin.valueChanged.connect(self._on_duration_changed)

        layout.addWidget(dur_label, 3, 0)
        layout.addWidget(self.dur_spin, 3, 1, 1, 2)  # Span 2 columns

        # Initially disabled until frame is activated
        self._set_widgets_enabled(False)

    def _set_widgets_enabled(self, enabled: bool) -> None:
        """Enable or disable all interactive widgets."""
        self.freq_spin.setEnabled(enabled and self.track_index < 3)  # Only tone channels
        self.vol_spin.setEnabled(enabled)
        self.dur_spin.setEnabled(enabled)
        self.btn_tone.setEnabled(enabled and self.track_index < 3)
        self.btn_noise.setEnabled(enabled and self.track_index < 3)
        self.btn_deactivate.setEnabled(enabled)

    def _on_data_changed(self) -> None:
        """Emit signal when data changes."""
        if self.is_filled and not self.is_continuation:
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

    def _on_duration_changed(self, value: int) -> None:
        """Duration spinbox changed - emit data and update continuations."""
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
            data["period"] = self.freq_spin.value()  # Use period instead of frequency
        elif self.track_index == 4:  # Envelope channel
            data["frequency"] = self.freq_spin.value()  # For now, placeholder

        self.data_changed.emit(self.track_index, self.frame_number, data)

    def set_highlighted(self, highlighted: bool) -> None:
        """Set playback position highlight."""
        self.is_highlighted = highlighted
        self.update()

    def set_selected(self, selected: bool) -> None:
        """Set selection state for copy/paste."""
        self.is_selected = selected
        self.update()

    def set_continuation(self, is_continuation: bool) -> None:
        """Mark this cell as continuation of a previous frame's duration."""
        self.is_continuation = is_continuation
        if is_continuation:
            # Continuation cells are disabled and show lighter background
            self._set_widgets_enabled(False)
            self.setStyleSheet("background-color: #3a3a3a;")  # Lighter charcoal
        else:
            self.setStyleSheet("")  # Reset to default
        self.update()

    def set_data(self, data: dict | None) -> None:
        """Set frame data and update widget values.

        Args:
            data: Frame data dict with frequency, volume, tone_enabled, noise_enabled, deactivated
                  or None for empty frame
        """
        self.frame_data = data
        self.is_filled = data is not None

        # Block signals while updating to avoid triggering data_changed
        self.freq_spin.blockSignals(True)
        self.vol_spin.blockSignals(True)
        self.dur_spin.blockSignals(True)
        self.btn_tone.blockSignals(True)
        self.btn_noise.blockSignals(True)
        self.btn_deactivate.blockSignals(True)

        if data is None:
            # Empty frame - disable widgets and reset to defaults
            self._set_widgets_enabled(False)
            self.freq_spin.setValue(440)
            self.vol_spin.setValue(0)  # Default to silent
            self.dur_spin.setValue(1)
            self.btn_tone.setChecked(True)
            self.btn_noise.setChecked(False)
            self.btn_deactivate.setChecked(False)
        else:
            # Load data from dict
            # Handle frequency or period based on track type
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

            # Enable widgets for filled frames
            self._set_widgets_enabled(True)

            # Update button styles
            self._update_button_style(self.btn_tone, self.btn_tone.isChecked(), QColor(0, 255, 100))
            self._update_button_style(
                self.btn_noise, self.btn_noise.isChecked(), QColor(0, 255, 100)
            )
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

    def set_filled(self, filled: bool) -> None:
        """Mark this cell as filled (has event data) - for backward compatibility."""
        if not filled:
            self.set_data(None)
        else:
            # Create default data based on track type
            if self.track_index < 3:  # Tone channels (A, B, C)
                default_data = {
                    "frequency": 440,
                    "volume": 0,
                    "tone_enabled": True,
                    "noise_enabled": False,
                    "deactivated": False,
                    "duration": 1,
                }
            elif self.track_index == 3:  # Noise channel
                default_data = {
                    "period": 1,  # Default noise period
                    "volume": 0,
                    "deactivated": False,
                    "duration": 1,
                }
            else:  # Envelope channel
                default_data = {
                    "frequency": 440,  # Placeholder for envelope
                    "volume": 0,
                    "deactivated": False,
                    "duration": 1,
                }
            self.set_data(default_data)

    def paintEvent(self, event) -> None:
        """Paint cell border based on state (highlighted, selected, continuation)."""
        super().paintEvent(event)  # Let Qt paint the background first
        painter = QPainter(self)

        # Draw border based on state
        if self.is_highlighted:
            painter.setPen(QPen(QColor(255, 255, 0), 3))  # Yellow for playback position
        elif self.is_selected:
            painter.setPen(QPen(QColor(0, 255, 255), 2))  # Cyan for selection
        elif self.is_continuation:
            painter.setPen(QPen(QColor(120, 120, 120), 1))  # Gray for continuation
        elif self.is_filled:
            painter.setPen(QPen(QColor(0, 170, 255), 1))  # Blue for filled
        else:
            painter.setPen(QPen(QColor(85, 85, 85), 1))  # Dark gray for empty

        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def mousePressEvent(self, event) -> None:
        """Handle click on this cell."""
        from PySide6.QtCore import Qt as QtCore_Qt

        # Ctrl+Click = toggle selection (for copy/paste)
        if event.modifiers() & QtCore_Qt.ControlModifier:
            self.set_selected(not self.is_selected)
        # Regular click on empty cell = create frame with defaults
        elif not self.is_filled and not self.is_continuation:
            self.set_filled(True)
        # Regular click = allow inline editing (widgets handle clicks themselves)
        else:
            self.clicked.emit(self.track_index, self.frame_number)

        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        """Handle double-click - emit signal for side panel editing."""
        self.clicked.emit(self.track_index, self.frame_number)
        super().mouseDoubleClickEvent(event)


class TrackTimeline(QGroupBox):
    """Timeline for a single track with MUTE/SOLO controls."""

    frame_clicked = Signal(int, int)  # (track_index, frame_number)
    data_changed = Signal(int, int, dict)  # (track_index, frame_number, data)
    mute_changed = Signal(int, bool)  # (track_index, is_muted)
    solo_changed = Signal(int, bool)  # (track_index, is_soloed)
    add_card_clicked = Signal(int)  # (track_index) - for condensed mode

    def __init__(
        self,
        track_index: int,
        track_name: str,
        num_frames: int = 1,  # Start with 1 frame per channel
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(track_name, parent)
        self.track_index = track_index
        self.track_name = track_name
        self.num_frames = num_frames
        self.cells: list[FrameCell] = []
        self.is_muted = False
        self.is_soloed = False
        self.is_condensed = False  # False = expanded (full grid), True = condensed (cards only)
        self.frame_data_store: dict[int, dict] = {}  # Store data for condensed mode

        # Gray panel styling with title spacing
        self.setStyleSheet(
            "QGroupBox { background-color: #3c3c3c; border: 2px solid #555; "
            "border-radius: 5px; margin-top: 20px; margin-bottom: 20px; "
            "padding-top: 30px; padding-left: 10px; padding-right: 10px; padding-bottom: 10px; "
            "font-weight: bold; }"
            "QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; "
            "padding: 4px 0px; margin-top: -5px; }"
        )

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)  # Moderate vertical space within track

        # Timeline row (label + cells)
        timeline_row = QHBoxLayout()
        timeline_row.setSpacing(4)

        # Frame cells container (horizontal scrollable)
        self.cells_container = QWidget()
        self.cells_layout = QHBoxLayout(self.cells_container)
        self.cells_layout.setSpacing(4)  # Increased spacing between cells
        self.cells_layout.setContentsMargins(0, 0, 0, 0)

        # Initially build in expanded mode
        self._build_expanded_cells()

        self.cells_layout.addStretch()
        timeline_row.addWidget(self.cells_container)
        main_layout.addLayout(timeline_row)

        # Controls row (MUTE, SOLO, Add Card buttons)
        controls_row = QHBoxLayout()
        controls_row.setSpacing(12)  # More spacing between control buttons

        self.btn_mute = QPushButton("MUTE")
        self.btn_mute.setCheckable(True)
        self.btn_mute.setFixedSize(70, 25)
        self.btn_mute.toggled.connect(self._on_mute_toggled)

        self.btn_solo = QPushButton("SOLO")
        self.btn_solo.setCheckable(True)
        self.btn_solo.setFixedSize(70, 25)
        self.btn_solo.toggled.connect(self._on_solo_toggled)

        self.btn_add_card = QPushButton("+ Add Card")
        self.btn_add_card.setFixedSize(90, 25)
        self.btn_add_card.clicked.connect(self._on_add_card_clicked)
        self.btn_add_card.setVisible(False)  # Only visible in condensed mode

        controls_row.addWidget(self.btn_mute)
        controls_row.addWidget(self.btn_solo)
        controls_row.addWidget(self.btn_add_card)
        controls_row.addStretch()

        main_layout.addLayout(controls_row)

        # Initialize button styles
        self._update_mute_style()
        self._update_solo_style()

    def _build_expanded_cells(self) -> None:
        """Build cells for expanded mode (full timeline grid)."""
        for frame_num in range(self.num_frames):
            cell = FrameCell(self.track_index, frame_num)
            cell.clicked.connect(self.frame_clicked)
            cell.data_changed.connect(self.data_changed)  # Forward data changes
            self.cells_layout.addWidget(cell)
            self.cells.append(cell)

            # Initialize first frame as active with volume 0
            if frame_num == 0:
                if self.track_index < 3:  # Tone channels (A, B, C)
                    default_data = {
                        "frequency": 440,
                        "volume": 0,
                        "tone_enabled": True,
                        "noise_enabled": False,
                        "deactivated": False,
                        "duration": 1,
                    }
                elif self.track_index == 3:  # Noise channel
                    default_data = {
                        "period": 1,  # Default noise period
                        "volume": 0,
                        "deactivated": False,
                        "duration": 1,
                    }
                else:  # Envelope channel (track 4)
                    default_data = {
                        "frequency": 440,  # Placeholder
                        "volume": 0,
                        "deactivated": False,
                        "duration": 1,
                    }
                cell.set_data(default_data)
                self.frame_data_store[frame_num] = default_data.copy()

    def _build_condensed_cells(self) -> None:
        """Build cells for condensed mode (only cards with data)."""
        # Sort frame numbers to display in order
        sorted_frames = sorted(self.frame_data_store.keys())
        for frame_num in sorted_frames:
            cell = FrameCell(self.track_index, frame_num)
            cell.clicked.connect(self.frame_clicked)
            cell.data_changed.connect(self.data_changed)
            self.cells_layout.addWidget(cell)
            self.cells.append(cell)
            # Load the stored data
            cell.set_data(self.frame_data_store[frame_num])

    def _on_mute_toggled(self, checked: bool) -> None:
        """Handle MUTE button toggle."""
        self.is_muted = checked
        self._update_mute_style()
        self.mute_changed.emit(self.track_index, checked)

    def _on_solo_toggled(self, checked: bool) -> None:
        """Handle SOLO button toggle."""
        self.is_soloed = checked
        self._update_solo_style()
        self.solo_changed.emit(self.track_index, checked)

    def _on_add_card_clicked(self) -> None:
        """Handle Add Card button in condensed mode."""
        self.add_card_clicked.emit(self.track_index)

    def _update_mute_style(self) -> None:
        """Update MUTE button appearance based on state."""
        if self.is_muted:
            self.btn_mute.setStyleSheet(
                "background-color: rgb(255, 100, 100); color: black; font-weight: bold;"
            )
        else:
            self.btn_mute.setStyleSheet("background-color: #555; color: #aaa;")

    def _update_solo_style(self) -> None:
        """Update SOLO button appearance based on state."""
        if self.is_soloed:
            self.btn_solo.setStyleSheet(
                "background-color: rgb(0, 255, 100); color: black; font-weight: bold;"
            )
        else:
            self.btn_solo.setStyleSheet("background-color: #555; color: #aaa;")

    def rebuild_cells(self, condensed: bool) -> None:
        """Rebuild cells for condensed or expanded mode.

        Args:
            condensed: True for condensed mode (cards only), False for expanded (full grid)
        """
        self.is_condensed = condensed

        # Clear existing cells
        for cell in self.cells:
            self.cells_layout.removeWidget(cell)
            cell.deleteLater()
        self.cells.clear()

        # Rebuild based on mode
        if condensed:
            self._build_condensed_cells()
            self.btn_add_card.setVisible(True)
        else:
            self._build_expanded_cells()
            self.btn_add_card.setVisible(False)
            # Restore data from store
            for frame_num, data in self.frame_data_store.items():
                if frame_num < len(self.cells):
                    self.cells[frame_num].set_data(data)

    def set_frame_filled(self, frame_number: int, filled: bool) -> None:
        """Mark a specific frame as filled or empty."""
        if 0 <= frame_number < len(self.cells):
            self.cells[frame_number].set_filled(filled)

    def set_frame_data(self, frame_number: int, data: dict | None) -> None:
        """Set frame data with visualization and handle duration/continuation.

        Args:
            frame_number: Frame index
            data: Frame data dict or None for empty
        """
        # Update data store (used for mode switching)
        if data is not None:
            self.frame_data_store[frame_number] = data.copy()
        elif frame_number in self.frame_data_store:
            del self.frame_data_store[frame_number]

        # Update cell if in expanded mode
        if not self.is_condensed and 0 <= frame_number < len(self.cells):
            # First, clear ALL old continuations starting from this frame
            # This handles duration shrinkage correctly
            self.clear_continuations_from(frame_number + 1)

            # Set the frame data
            self.cells[frame_number].set_data(data)

            # Handle duration - mark subsequent cells as continuation
            if data is not None and data.get("duration", 1) > 1:
                duration = int(data["duration"])
                # Mark cells as continuation for the duration
                for i in range(1, duration):
                    continuation_idx = frame_number + i
                    if continuation_idx < len(self.cells):
                        self.cells[continuation_idx].set_continuation(True)
            else:
                # Clear continuation on this cell if duration is 1
                self.cells[frame_number].set_continuation(False)
        elif self.is_condensed:
            # In condensed mode, rebuild to show/hide cards dynamically
            self.rebuild_cells(True)

    def clear_continuations_from(self, start_frame: int) -> None:
        """Clear continuation markers from a frame onwards.

        Args:
            start_frame: Frame number to start clearing from
        """
        # Clear all continuations from this point (useful when editing)
        for i in range(start_frame, len(self.cells)):
            if self.cells[i].is_continuation:
                self.cells[i].set_continuation(False)
            else:
                break  # Stop when we hit a non-continuation cell


class FrameTimeline(QWidget):
    """Complete timeline view with all tracks and MUTE/SOLO controls."""

    frame_clicked = Signal(int, int)  # (track_index, frame_number)
    data_changed = Signal(int, int, dict)  # (track_index, frame_number, data)
    frames_copied = Signal(int)  # (count)
    frames_pasted = Signal(list)  # [(track_index, frame_number, data), ...]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.num_frames = 1  # Start with 1 frame per channel
        self.tracks: list[TrackTimeline] = []
        self.clipboard = []  # Store copied frame data: [(track_idx, frame_num, data), ...]
        self.setFocusPolicy(Qt.StrongFocus)  # Allow keyboard events
        self.is_condensed = False  # Start in expanded mode by default

        layout = QVBoxLayout(self)
        layout.setSpacing(15)  # Moderate vertical space between tracks
        layout.setContentsMargins(10, 10, 10, 10)  # Add margins around entire timeline

        # Controls row with mode toggle
        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)

        self.btn_toggle_mode = QPushButton("Expanded")  # Start in expanded mode
        self.btn_toggle_mode.setCheckable(True)
        self.btn_toggle_mode.setChecked(False)  # Start unchecked (expanded mode)
        self.btn_toggle_mode.setFixedSize(100, 30)
        self.btn_toggle_mode.toggled.connect(self._on_mode_toggled)
        self.btn_toggle_mode.setStyleSheet(
            "QPushButton { background-color: #555; color: #ccc; font-weight: bold; }"
            "QPushButton:checked { background-color: #0a7; color: white; }"
        )
        controls_row.addWidget(QLabel("View Mode:"))
        controls_row.addWidget(self.btn_toggle_mode)
        controls_row.addStretch()

        layout.addLayout(controls_row)

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
        cell_width = 100  # Updated to match new FrameCell width (reduced from 120)
        cell_spacing = 4  # Match cells_layout spacing
        for i in range(0, self.num_frames, marker_interval):
            # Show time in seconds
            seconds = i // 60
            marker = QLabel(f"{seconds}s")
            # Account for spacing between cells
            marker.setFixedWidth((cell_width + cell_spacing) * marker_interval - cell_spacing)
            marker.setStyleSheet("color: #888; font-size: 9px;")
            frame_markers_layout.addWidget(marker)

        frame_markers_layout.addStretch()
        header_row.addWidget(frame_markers)
        layout.addLayout(header_row)

        # Create track timelines with MUTE/SOLO
        track_names = ["Channel A", "Channel B", "Channel C", "Noise", "Envelope"]
        for idx, name in enumerate(track_names):
            track = TrackTimeline(idx, name, self.num_frames)
            track.frame_clicked.connect(self.frame_clicked)
            track.data_changed.connect(self.data_changed)  # Forward data changes
            track.mute_changed.connect(self._on_track_mute_changed)
            track.solo_changed.connect(self._on_track_solo_changed)
            layout.addWidget(track)
            self.tracks.append(track)
            # Starts in expanded mode by default (cells already built in __init__)

    def _on_mode_toggled(self, checked: bool) -> None:
        """Handle mode toggle button - switch between condensed and expanded."""
        self.is_condensed = checked
        mode_text = "Condensed" if checked else "Expanded"
        self.btn_toggle_mode.setText(mode_text)

        # Rebuild all tracks with new mode
        for track in self.tracks:
            track.rebuild_cells(self.is_condensed)

    def _on_track_mute_changed(self, track_index: int, is_muted: bool) -> None:
        """Handle track MUTE button - propagate to main window audio control."""
        # Main window will handle audio muting
        pass

    def _on_track_solo_changed(self, track_index: int, is_soloed: bool) -> None:
        """Handle track SOLO button - mute all other non-SOLO'd tracks."""
        # If any track is SOLO'd, mute all non-SOLO'd tracks
        any_soloed = any(track.is_soloed for track in self.tracks)

        if any_soloed:
            # SOLO mode: mute tracks that aren't solo'd
            for track in self.tracks:
                if not track.is_soloed and not track.is_muted:
                    # Visually indicate this track is muted due to SOLO
                    # but don't change the MUTE button state
                    pass
        # Main window will handle SOLO logic in audio playback

    def set_frame_data(self, track_index: int, frame_number: int, data: dict | None | bool) -> None:
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

    def keyPressEvent(self, event) -> None:
        """Handle keyboard shortcuts for copy/paste."""
        from PySide6.QtGui import QKeySequence

        if event.matches(QKeySequence.Copy):  # Ctrl+C
            self._copy_selected()
        elif event.matches(QKeySequence.Paste):  # Ctrl+V
            self._paste()
        elif event.matches(QKeySequence.SelectAll):  # Ctrl+A
            self._select_all()
        else:
            super().keyPressEvent(event)

    def _copy_selected(self) -> None:
        """Copy selected frames to clipboard."""
        self.clipboard = []
        for track_idx, track in enumerate(self.tracks):
            for cell in track.cells:
                if cell.is_selected and cell.frame_data:
                    self.clipboard.append((track_idx, cell.frame_number, cell.frame_data.copy()))

        # Emit signal with count for status bar feedback
        if self.clipboard:
            self.frames_copied.emit(len(self.clipboard))

    def _paste(self) -> None:
        """Paste clipboard data - emit signal for main window to handle."""
        if self.clipboard:
            # Emit signal with clipboard data for main window to apply
            self.frames_pasted.emit(self.clipboard)

    def get_clipboard_info(self) -> str:
        """Get human-readable clipboard info for status messages."""
        if not self.clipboard:
            return "Clipboard empty"
        return f"{len(self.clipboard)} frame(s) copied"

    def _select_all(self) -> None:
        """Select all filled frames."""
        for track in self.tracks:
            for cell in track.cells:
                if cell.is_filled:
                    cell.set_selected(True)


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
        self.vol_spin.setValue(0)  # Default to silent
        self.vol_spin.setEnabled(False)
        vol_row.addWidget(self.vol_spin)
        vol_row.addStretch()
        layout.addLayout(vol_row)

        # Duration control (frames at 60 FPS)
        dur_row = QHBoxLayout()
        dur_row.addWidget(QLabel("Duration (frames):"))
        self.dur_spin = QSpinBox()
        self.dur_spin.setRange(1, 300)  # 1-300 frames (up to 5 seconds at 60 FPS)
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

        # Collect frame data from UI controls
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
        self.freq_spin.setEnabled(track_index < 3)  # Only for tone channels
        self.vol_spin.setEnabled(True)
        self.dur_spin.setEnabled(True)  # Duration available for all tracks
        self.btn_tone_enable.setEnabled(track_index < 3)
        self.btn_noise_enable.setEnabled(track_index < 3)
        self.btn_apply.setEnabled(True)
        self.btn_clear.setEnabled(True)

    def load_frame_data(self, data: dict | None) -> None:
        """Load frame data into the editor controls.

        Args:
            data: Frame data dict with frequency, volume, duration, tone_enabled, noise_enabled
                  or None for empty frame (resets to defaults)
        """
        if data is None:
            # Reset to defaults for empty frame
            self.freq_spin.setValue(440)
            self.vol_spin.setValue(0)  # Default to silent
            self.dur_spin.setValue(1)
            self.btn_tone_enable.setChecked(True)
            self.btn_noise_enable.setChecked(False)
        else:
            # Load data from frame
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
