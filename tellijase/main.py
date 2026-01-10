"""Application bootstrap for telliJASE."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QSlider,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from tellijase import __version__
from tellijase.audio.stream import LivePSGStream, SOUNDDEVICE_AVAILABLE
from tellijase.audio.pygame_player import PygamePSGPlayer, PYGAME_AVAILABLE
from tellijase.models import PSGState
from tellijase.storage import (
    JamSession,
    Project,
    Song,
    TrackEvent,
    load_project,
    new_project,
    save_project,
)
from tellijase.ui.jam_controls import ChannelControl
from tellijase.ui.timeline import FrameTimeline, FrameEditor
from tellijase.psg.utils import frequency_to_period

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """telliJASE main window with JAM + FRAME placeholders."""

    def __init__(self) -> None:
        super().__init__()

        # Models (domain layer - pure data)
        self.project: Project = new_project()
        self.current_state = PSGState()  # Live JAM state
        self.current_file: Optional[Path] = None

        # FRAME mode state
        self.current_song: Optional[Song] = None
        # Timeline data: {"A": {frame: data}, "B": {frame: data}, ...}
        self.timeline_data: dict[str, dict[int, dict]] = {
            "A": {},
            "B": {},
            "C": {},
            "N": {},
            "E": {},  # Envelope
        }

        # Frame playback state
        self.playback_timer: Optional[QTimer] = None
        self.current_frame = 0
        self.is_playing = False
        self.playback_loop = False

        # UI widgets
        self.channel_controls: list[ChannelControl] = []

        # Audio - try sounddevice first, fall back to pygame
        self.audio_stream = None
        self.audio_backend = None
        self.audio_available = False

        # Try sounddevice (best for real-time)
        if SOUNDDEVICE_AVAILABLE:
            try:
                self.audio_stream = LivePSGStream(self.current_state)
                self.audio_backend = "sounddevice"
                self.audio_available = True
                logger.info("Audio initialized with sounddevice")
            except Exception as e:
                logger.warning(f"sounddevice failed: {e}, trying pygame...")

        # Fall back to pygame if sounddevice failed
        if not self.audio_available and PYGAME_AVAILABLE:
            try:
                self.audio_stream = PygamePSGPlayer(self.current_state)
                self.audio_backend = "pygame"
                self.audio_available = True
                logger.info("Audio initialized with pygame.mixer")
            except Exception as e:
                logger.error(f"pygame audio failed: {e}")

        if not self.audio_available:
            logger.warning("No audio backend available")

        self.setMinimumSize(1280, 768)
        self.resize(1600, 900)

        self._create_actions()
        self._create_menus()
        self._create_status_bar()
        self._create_tabs()
        self._connect_signals()
        self._update_title()
        self._initialize_jam_controls()

        # Check audio availability after UI is ready
        if not self.audio_available:
            QTimer.singleShot(100, self._warn_audio_missing)

    # UI Construction -------------------------------------------------
    def _create_actions(self) -> None:
        self.action_new = self._make_action("&New", "Ctrl+N", self.new_project)
        self.action_open = self._make_action("&Open…", "Ctrl+O", self.open_project)
        self.action_save = self._make_action("&Save", "Ctrl+S", self.save_project)
        self.action_save_as = self._make_action("Save &As…", "Ctrl+Shift+S", self.save_project_as)
        self.action_quit = self._make_action("&Quit", "Ctrl+Q", self.close)

    def _create_menus(self) -> None:
        menubar = QMenuBar(self)
        file_menu = QMenu("&File", self)
        file_menu.addAction(self.action_new)
        file_menu.addAction(self.action_open)
        file_menu.addSeparator()
        file_menu.addAction(self.action_save)
        file_menu.addAction(self.action_save_as)
        file_menu.addSeparator()
        file_menu.addAction(self.action_quit)
        menubar.addMenu(file_menu)

        # Help menu
        help_menu = QMenu("&Help", self)
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        menubar.addMenu(help_menu)

        self.setMenuBar(menubar)

    def _create_status_bar(self) -> None:
        status = QStatusBar()
        status.showMessage("Ready")
        self.setStatusBar(status)

    def _create_tabs(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_jam_tab(), "JAM")
        self.tabs.addTab(self._build_frame_tab(), "FRAME")
        layout.addWidget(self.tabs)

        self.setCentralWidget(container)

    def _build_jam_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        layout.addWidget(QLabel("<h3>JAM Sessions</h3>"))
        layout.addWidget(QLabel("Realtime AY-3-8914 playground. Capture snapshots as sessions."))

        # Session management row (like telliGRAM's animation dropdown)
        session_row = QHBoxLayout()
        session_row.addWidget(QLabel("Saved Sessions:"))
        self.session_combo = QComboBox()
        self.session_combo.setMinimumWidth(200)
        self.session_combo.currentIndexChanged.connect(self._on_session_selected)
        session_row.addWidget(self.session_combo)

        self.btn_load_session = QPushButton("Load")
        self.btn_load_session.clicked.connect(self._on_load_session)
        session_row.addWidget(self.btn_load_session)

        self.btn_save_session = QPushButton("Save Current")
        self.btn_save_session.clicked.connect(self._on_save_current_session)
        session_row.addWidget(self.btn_save_session)

        self.btn_new_session = QPushButton("New Session...")
        self.btn_new_session.clicked.connect(self._on_new_session)
        session_row.addWidget(self.btn_new_session)

        session_row.addStretch()
        layout.addLayout(session_row)

        # Playback controls
        button_row = QHBoxLayout()
        self.btn_play = QPushButton("Play Preview")
        self.btn_stop = QPushButton("Stop")
        button_row.addWidget(self.btn_play)
        button_row.addWidget(self.btn_stop)
        button_row.addStretch()
        layout.addLayout(button_row)

        channel_row = QHBoxLayout()
        for idx in range(3):
            control = ChannelControl(idx)
            channel_row.addWidget(control)
            self.channel_controls.append(control)
        layout.addLayout(channel_row)

        # Noise period control (shared across all channels)
        noise_group = QGroupBox("Noise")
        noise_layout = QVBoxLayout(noise_group)
        noise_layout.setContentsMargins(20, 10, 20, 10)

        self.noise_label = QLabel("Period: 1 (~111861 Hz)")
        noise_layout.addWidget(self.noise_label)

        # Horizontal layout with slider and text input
        noise_row = QHBoxLayout()
        self.noise_slider = QSlider(Qt.Horizontal)
        self.noise_slider.setRange(0, 31)  # R6 is 5 bits (0-31)
        self.noise_slider.setValue(1)  # Start at 1 (ready to use, not OFF)
        self.noise_slider.setTickPosition(QSlider.TicksBelow)
        self.noise_slider.setTickInterval(1)  # Tick for each period value
        self.noise_slider.setPageStep(1)  # Click on track moves by 1
        self.noise_slider.valueChanged.connect(self._on_noise_slider_changed)

        self.noise_input = QLineEdit()
        self.noise_input.setMaximumWidth(70)
        self.noise_input.setText("1")
        self.noise_input.editingFinished.connect(self._on_noise_input_changed)

        noise_row.addWidget(self.noise_slider)
        noise_row.addWidget(self.noise_input)
        noise_layout.addLayout(noise_row)

        layout.addWidget(noise_group)

        # Register value display (split: INPUT | OUTPUT)
        register_group = QWidget()
        register_layout = QVBoxLayout(register_group)
        register_layout.setContentsMargins(20, 10, 20, 10)

        register_layout.addWidget(QLabel("<b>PSG Chip I/O:</b>"))

        # Horizontal split for input/output
        io_row = QHBoxLayout()

        # LEFT: Input (raw register values)
        input_group = QWidget()
        input_layout = QVBoxLayout(input_group)
        input_layout.setContentsMargins(0, 0, 5, 0)
        input_layout.addWidget(QLabel("<i>Input (Register Values):</i>"))

        self.register_input_display = QLabel()
        self.register_input_display.setFont(QApplication.font("Monospace"))
        self.register_input_display.setStyleSheet(
            "background-color: #1e1e1e; color: #00ff00; padding: 10px; "
            "font-family: monospace; font-size: 9pt;"
        )
        self.register_input_display.setWordWrap(False)
        self.register_input_display.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        input_layout.addWidget(self.register_input_display)

        # RIGHT: Output (decoded values)
        output_group = QWidget()
        output_layout = QVBoxLayout(output_group)
        output_layout.setContentsMargins(5, 0, 0, 0)
        output_layout.addWidget(QLabel("<i>Output (Actual Sound):</i>"))

        self.register_output_display = QLabel()
        self.register_output_display.setFont(QApplication.font("Monospace"))
        self.register_output_display.setStyleSheet(
            "background-color: #1e1e1e; color: #00aaff; padding: 10px; "
            "font-family: monospace; font-size: 9pt;"
        )
        self.register_output_display.setWordWrap(False)
        self.register_output_display.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        output_layout.addWidget(self.register_output_display)

        io_row.addWidget(input_group)
        io_row.addWidget(output_group)
        register_layout.addLayout(io_row)

        layout.addWidget(register_group)

        self.jam_status_label = QLabel("PSG state ready.")
        layout.addWidget(self.jam_status_label)

        layout.addStretch()
        return widget

    def _build_frame_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

        layout.addWidget(QLabel("<h3>FRAME Sequencer</h3>"))
        layout.addWidget(QLabel("Tracker-style timeline for frame-by-frame composition."))

        # Sequence management row (like JAM sessions dropdown)
        sequence_row = QHBoxLayout()
        sequence_row.addWidget(QLabel("Sequences:"))
        self.sequence_combo = QComboBox()
        self.sequence_combo.setMinimumWidth(200)
        self.sequence_combo.currentIndexChanged.connect(self._on_sequence_selected)
        sequence_row.addWidget(self.sequence_combo)

        self.btn_load_sequence = QPushButton("Load")
        self.btn_load_sequence.clicked.connect(self._on_load_sequence)
        sequence_row.addWidget(self.btn_load_sequence)

        self.btn_save_sequence = QPushButton("Save Current")
        self.btn_save_sequence.clicked.connect(self._on_save_current_sequence)
        sequence_row.addWidget(self.btn_save_sequence)

        self.btn_new_sequence = QPushButton("New Sequence...")
        self.btn_new_sequence.clicked.connect(self._on_new_sequence)
        sequence_row.addWidget(self.btn_new_sequence)

        sequence_row.addStretch()
        layout.addLayout(sequence_row)

        # Transport controls
        transport = QHBoxLayout()
        self.btn_frame_play = QPushButton("Play")
        self.btn_frame_pause = QPushButton("Pause")
        self.btn_frame_stop = QPushButton("Stop")
        self.btn_frame_loop = QPushButton("Loop")
        self.btn_frame_loop.setCheckable(True)

        # Connect transport controls
        self.btn_frame_play.clicked.connect(self._on_frame_play)
        self.btn_frame_pause.clicked.connect(self._on_frame_pause)
        self.btn_frame_stop.clicked.connect(self._on_frame_stop)
        self.btn_frame_loop.toggled.connect(self._on_frame_loop_toggled)

        for btn in (
            self.btn_frame_play,
            self.btn_frame_pause,
            self.btn_frame_stop,
            self.btn_frame_loop,
        ):
            transport.addWidget(btn)

        transport.addStretch()
        layout.addLayout(transport)

        # Main timeline and editor layout
        content_layout = QHBoxLayout()

        # Timeline (scrollable)
        from PySide6.QtWidgets import QScrollArea

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.timeline = FrameTimeline()
        self.timeline.frame_clicked.connect(self._on_frame_clicked)
        self.timeline.data_changed.connect(self._on_frame_applied)  # Inline editing
        self.timeline.frames_copied.connect(self._on_frames_copied)
        self.timeline.frames_pasted.connect(self._on_frames_pasted)
        scroll.setWidget(self.timeline)
        content_layout.addWidget(scroll, stretch=3)

        # Frame editor panel
        self.frame_editor = FrameEditor()
        self.frame_editor.frame_applied.connect(self._on_frame_applied)
        self.frame_editor.frame_cleared.connect(self._on_frame_cleared)
        content_layout.addWidget(self.frame_editor, stretch=1)

        layout.addLayout(content_layout, stretch=1)
        return widget

    def _connect_signals(self) -> None:
        """Connect UI signals to model updates - clean model-view separation."""
        self.btn_play.clicked.connect(self._on_play_audio)
        self.btn_stop.clicked.connect(self._on_stop_audio)

        # Connect high-level channel signals to model updates
        for idx, control in enumerate(self.channel_controls):
            # Get the channel model
            if idx == 0:
                channel = self.current_state.channel_a
            elif idx == 1:
                channel = self.current_state.channel_b
            else:
                channel = self.current_state.channel_c

            # Wire signals to model (direct field assignment + register display update)
            control.frequency_changed.connect(
                lambda freq, ch=channel: self._update_channel_param(ch, "frequency", freq)
            )
            control.volume_changed.connect(
                lambda vol, ch=channel: self._update_channel_param(ch, "volume", vol)
            )
            control.tone_enabled_changed.connect(
                lambda enabled, ch=channel: self._update_channel_param(ch, "tone_enabled", enabled)
            )
            control.noise_enabled_changed.connect(
                lambda enabled, ch=channel: self._update_channel_param(ch, "noise_enabled", enabled)
            )

    def _initialize_jam_controls(self) -> None:
        """Initialize JAM controls with current model state."""
        for control in self.channel_controls:
            control.emit_state()

        # Update register display with initial state
        self._update_register_display()

        # Populate session dropdown
        self._refresh_session_list()

        # Populate sequence dropdown
        self._refresh_sequence_list()

        if not self.audio_available:
            self.btn_play.setEnabled(False)
            self.btn_stop.setEnabled(False)
            self.jam_status_label.setText("⚠️ Audio unavailable (no backend found)")
            self.jam_status_label.setStyleSheet("color: orange; font-weight: bold;")
        else:
            self.jam_status_label.setText(f"Audio: {self.audio_backend}")
            self.jam_status_label.setStyleSheet("color: green;")

    def _make_action(self, text: str, shortcut: str, handler) -> QAction:
        action = QAction(text, self)
        action.setShortcut(shortcut)
        action.triggered.connect(handler)
        return action

    # File Handling ---------------------------------------------------
    def new_project(self) -> None:
        """Create a new project with default PSG state."""
        self.project = new_project()
        self.current_file = None
        self.current_state = PSGState()  # Fresh state with default values
        self._initialize_jam_controls()
        self.statusBar().showMessage("Created new project", 3000)
        self._update_title()

    def open_project(self) -> None:
        """Open a project file from disk."""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open telliJASE Project",
            "",
            "telliJASE Projects (*.tellijase);;All Files (*)",
        )
        if not filename:
            return
        try:
            self.project = load_project(filename)
            self.current_file = Path(filename)
            self.current_state = PSGState()  # Fresh state
            self._initialize_jam_controls()
            self.statusBar().showMessage(f"Opened {filename}", 3000)
            self._update_title()
        except Exception as exc:  # pragma: no cover - UI popup
            QMessageBox.critical(self, "Open Failed", str(exc))

    def save_project(self) -> None:
        if self.current_file is None:
            self.save_project_as()
            return
        try:
            save_project(self.project, self.current_file)
            self.statusBar().showMessage(f"Saved {self.current_file}", 3000)
        except Exception as exc:  # pragma: no cover - UI popup
            QMessageBox.critical(self, "Save Failed", str(exc))

    def save_project_as(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save telliJASE Project",
            "",
            "telliJASE Projects (*.tellijase);;All Files (*)",
        )
        if not filename:
            return
        path = Path(filename)
        if path.suffix != ".tellijase":
            path = path.with_suffix(".tellijase")
        try:
            self.current_file = save_project(self.project, path)
            self.statusBar().showMessage(f"Saved {self.current_file}", 3000)
            self._update_title()
        except Exception as exc:  # pragma: no cover - UI popup
            QMessageBox.critical(self, "Save Failed", str(exc))

    def show_about(self) -> None:
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About telliJASE",
            f"<h2>telliJASE v{__version__}</h2>"
            "<p><b>J</b>ust <b>A</b> <b>S</b>ound <b>E</b>ditor "
            "for the Intellivision AY-3-8914 PSG</p>"
            "<p>Create custom music and sound effects using the General "
            "Instrument AY-3-8914 Programmable Sound Generator chip found "
            "in the Intellivision game console</p>"
            "<p>© 2025-2026 Andrew Potozniak (Tyraziel & 1.z3r0)</p>"
            "<p>Dual licensed under the "
            "<a href='https://opensource.org/licenses/MIT'>MIT License</a> "
            "and <a href='https://github.com/tyraziel/vibe-coder-license'>"
            "VCL-0.1-Experimental</a></p>"
            "<p><small>Intellivision and Intellivision trademarks are "
            "the property of Atari Interactive, Inc. "
            "This application is built to aid sound programming "
            "for the Intellivision. "
            "This project is not affiliated with or endorsed by "
            "Atari Interactive, Inc.</small></p>"
            "<p><i><a href='https://aiattribution.github.io/statements/"
            "AIA-PAI-Nc-Hin-R-?model=Claude%20Code%20%5BSonnet%204.5%5D-v1.0'>"
            "AIA PAI Nc Hin R Claude Code [Sonnet 4.5] v1.0</a></i></p>",
        )

    # JAM Mode Callbacks ----------------------------------------------
    def _refresh_session_list(self) -> None:
        """Refresh the session dropdown with current project sessions."""
        self.session_combo.blockSignals(True)
        self.session_combo.clear()

        if not self.project.jam_sessions:
            self.session_combo.addItem("(No saved sessions)")
            self.session_combo.setEnabled(False)
            self.btn_load_session.setEnabled(False)
        else:
            for session in self.project.jam_sessions:
                self.session_combo.addItem(session.name)
            self.session_combo.setEnabled(True)
            self.btn_load_session.setEnabled(True)
            # Select the last session by default
            self.session_combo.setCurrentIndex(len(self.project.jam_sessions) - 1)

        self.session_combo.blockSignals(False)

    def _on_session_selected(self, index: int) -> None:
        """Session dropdown selection changed."""
        # Just update UI to show which session is selected
        # Actual loading happens when Load button is clicked
        pass

    def _on_new_session(self) -> None:
        """Create a new JAM session with current state."""
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(
            self,
            "New JAM Session",
            "Session name:",
            QLineEdit.Normal,
            f"Session {len(self.project.jam_sessions) + 1}",
        )

        if not ok or not name.strip():
            return

        new_id = f"jam-{datetime.utcnow().timestamp()}"
        session = JamSession(
            id=new_id,
            name=name.strip(),
            registers=self.current_state.to_registers(),
        )
        self.project.jam_sessions.append(session)
        self.project.touch()
        self._refresh_session_list()
        self.statusBar().showMessage(f"Created session: {session.name}", 3000)

    def _on_save_current_session(self) -> None:
        """Save current PSG state to the selected session."""
        if not self.project.jam_sessions:
            self._on_new_session()
            return

        index = self.session_combo.currentIndex()
        if index < 0 or index >= len(self.project.jam_sessions):
            return

        session = self.project.jam_sessions[index]
        session.registers = self.current_state.to_registers()
        session.updated = datetime.utcnow().isoformat()
        self.project.touch()
        self.statusBar().showMessage(f"Saved to session: {session.name}", 3000)

    def _on_load_session(self) -> None:
        """Load selected session into current JAM controls."""
        if not self.project.jam_sessions:
            return

        index = self.session_combo.currentIndex()
        if index < 0 or index >= len(self.project.jam_sessions):
            return

        session = self.project.jam_sessions[index]

        # Load PSG state from session registers
        self.current_state = PSGState.from_registers(session.registers)

        # Update all UI controls from the loaded state
        for idx, control in enumerate(self.channel_controls):
            if idx == 0:
                channel = self.current_state.channel_a
            elif idx == 1:
                channel = self.current_state.channel_b
            else:
                channel = self.current_state.channel_c

            control.set_state(
                frequency=channel.frequency,
                volume=channel.volume,
                tone_enabled=channel.tone_enabled,
                noise_enabled=channel.noise_enabled,
            )

        # Update noise control
        self.noise_slider.setValue(self.current_state.noise_period)

        # Update register display
        self._update_register_display()

        self.statusBar().showMessage(f"Loaded session: {session.name}", 3000)

    # FRAME Mode Callbacks --------------------------------------------
    def _refresh_sequence_list(self) -> None:
        """Refresh the sequence dropdown with current project songs."""
        self.sequence_combo.blockSignals(True)
        self.sequence_combo.clear()

        if not self.project.songs:
            self.sequence_combo.addItem("(No saved sequences)")
            self.sequence_combo.setEnabled(False)
            self.btn_load_sequence.setEnabled(False)
        else:
            for song in self.project.songs:
                self.sequence_combo.addItem(song.name)
            self.sequence_combo.setEnabled(True)
            self.btn_load_sequence.setEnabled(True)
            # Select the last sequence by default
            self.sequence_combo.setCurrentIndex(len(self.project.songs) - 1)

        self.sequence_combo.blockSignals(False)

    def _on_sequence_selected(self, index: int) -> None:
        """Sequence dropdown selection changed."""
        # Just update UI to show which sequence is selected
        # Actual loading happens when Load button is clicked
        pass

    def _on_new_sequence(self) -> None:
        """Create a new FRAME sequence."""
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(
            self,
            "New Sequence",
            "Sequence name:",
            QLineEdit.Normal,
            f"Sequence {len(self.project.songs) + 1}",
        )

        if not ok or not name.strip():
            return

        new_id = f"song-{datetime.utcnow().timestamp()}"
        song = Song(
            id=new_id,
            name=name.strip(),
            bpm=120,
            loop=False,
            tracks={},  # Empty timeline
        )
        self.project.songs.append(song)
        self.project.touch()
        self._refresh_sequence_list()
        self.statusBar().showMessage(f"Created sequence: {song.name}", 3000)

    def _on_save_current_sequence(self) -> None:
        """Save current timeline to the selected sequence."""
        if not self.project.songs:
            self._on_new_sequence()
            return

        index = self.sequence_combo.currentIndex()
        if index < 0 or index >= len(self.project.songs):
            return

        song = self.project.songs[index]

        # Convert timeline_data to TrackEvent objects
        song.tracks = {}
        for channel_id, frames in self.timeline_data.items():
            if not frames:
                continue  # Skip empty tracks

            events = []
            for frame_num, data in sorted(frames.items()):
                # Convert frequency to period for storage
                period = None
                if data.get("frequency") is not None:
                    period = frequency_to_period(data["frequency"])

                event = TrackEvent(
                    frame=frame_num,
                    duration=data.get("duration", 1),  # Get duration from frame data
                    period=period,
                    volume=data.get("volume"),
                    noise_period=None,  # Handled by noise track
                    noise=data.get("noise_enabled"),
                )
                events.append(event)

            if events:
                song.tracks[channel_id] = events

        song.updated = datetime.utcnow().isoformat()  # type: ignore
        self.project.touch()
        self.statusBar().showMessage(
            f"Saved {sum(len(e) for e in song.tracks.values())} "
            f"events to sequence: {song.name}",
            3000,
        )

    def _on_load_sequence(self) -> None:
        """Load selected sequence into timeline."""
        if not self.project.songs:
            return

        index = self.sequence_combo.currentIndex()
        if index < 0 or index >= len(self.project.songs):
            return

        song = self.project.songs[index]
        self.current_song = song

        # Clear existing timeline data
        for channel_id in self.timeline_data:
            self.timeline_data[channel_id] = {}

        # Clear timeline UI
        for track_idx in range(5):
            for frame_num in range(128):
                self.timeline.set_frame_data(track_idx, frame_num, None)

        # Load TrackEvents into timeline_data
        event_count = 0
        for channel_id, events in song.tracks.items():
            for event in events:
                # Convert period back to frequency
                frequency = None
                if event.period is not None:
                    from tellijase.psg.utils import period_to_frequency

                    frequency = period_to_frequency(event.period)

                # Build frame data
                data = {
                    "frequency": frequency,
                    "volume": event.volume,
                    "tone_enabled": event.period is not None,  # Has tone if period set
                    "noise_enabled": event.noise,
                }

                # Store in timeline_data
                self.timeline_data[channel_id][event.frame] = data

                # Update timeline UI with visualization
                track_idx = {"A": 0, "B": 1, "C": 2, "N": 3, "E": 4}.get(channel_id, 0)
                self.timeline.set_frame_data(track_idx, event.frame, data)

                event_count += 1

        self.statusBar().showMessage(
            f"Loaded {event_count} events from sequence: {song.name}", 3000
        )

    def _track_index_to_channel_id(self, track_index: int) -> str:
        """Convert track index to channel ID."""
        mapping = {0: "A", 1: "B", 2: "C", 3: "N", 4: "E"}
        return mapping.get(track_index, "A")

    def _on_frame_clicked(self, track_index: int, frame_number: int) -> None:
        """Frame cell clicked - open editor for that frame."""
        self.frame_editor.set_frame(track_index, frame_number)

        # Load existing frame data if present
        channel_id = self._track_index_to_channel_id(track_index)
        frame_data = self.timeline_data[channel_id].get(frame_number)
        self.frame_editor.load_frame_data(frame_data)

        self.statusBar().showMessage(f"Editing Track {track_index} Frame {frame_number}", 2000)

    def _on_frame_applied(self, track_index: int, frame_number: int, data: dict) -> None:
        """Frame data applied - store in timeline and update UI."""
        channel_id = self._track_index_to_channel_id(track_index)

        # Store frame data
        self.timeline_data[channel_id][frame_number] = data

        # Update timeline cell with visualization
        self.timeline.set_frame_data(track_index, frame_number, data)

        self.statusBar().showMessage(
            f"Applied frame data to Track {track_index} Frame {frame_number}", 2000
        )

    def _on_frame_cleared(self, track_index: int, frame_number: int) -> None:
        """Frame cleared - remove from timeline."""
        channel_id = self._track_index_to_channel_id(track_index)

        # Remove frame data if it exists
        if frame_number in self.timeline_data[channel_id]:
            del self.timeline_data[channel_id][frame_number]

        # Update timeline cell to show empty
        self.timeline.set_frame_data(track_index, frame_number, None)

        # Reset editor to defaults
        self.frame_editor.load_frame_data(None)

        self.statusBar().showMessage(f"Cleared Track {track_index} Frame {frame_number}", 2000)

    def _on_frames_copied(self, count: int) -> None:
        """Handle frames copied to clipboard.

        Args:
            count: Number of frames copied
        """
        self.statusBar().showMessage(f"Copied {count} frame(s)", 2000)

    def _on_frames_pasted(self, clipboard_data: list) -> None:
        """Handle pasted frames from clipboard.

        Args:
            clipboard_data: List of (track_idx, frame_num, data) tuples
        """
        for track_idx, original_frame, data in clipboard_data:
            channel_id = self._track_index_to_channel_id(track_idx)

            # Store frame data copy
            self.timeline_data[channel_id][original_frame] = data.copy()

            # Update timeline cell with visualization
            self.timeline.set_frame_data(track_idx, original_frame, data)

        self.statusBar().showMessage(f"Pasted {len(clipboard_data)} frame(s)", 2000)

    # Frame Playback Engine -------------------------------------------
    def _on_frame_play(self) -> None:
        """Start frame playback."""
        if not self.audio_available:
            self._warn_audio_missing()
            return

        # Try current backend (same logic as JAM mode)
        if self.audio_stream and self.audio_stream.start():
            self._start_frame_playback()
            return

        # Current backend failed - try fallback to pygame
        if self.audio_backend == "sounddevice" and PYGAME_AVAILABLE:
            logger.warning("sounddevice failed to start, falling back to pygame")
            try:
                self.audio_stream = PygamePSGPlayer(self.current_state)
                self.audio_backend = "pygame"
                if self.audio_stream.start():
                    self._start_frame_playback()
                    self.statusBar().showMessage("Playing with pygame (fallback)...", 0)
                    return
            except Exception as e:
                logger.error(f"pygame fallback failed: {e}")

        # All backends failed
        QMessageBox.warning(
            self,
            "Playback Failed",
            f"Failed to start audio with {self.audio_backend}.\n\n"
            "Check console for errors. Audio may not be available in this environment.",
        )

    def _start_frame_playback(self) -> None:
        """Start the frame playback timer (separated for reuse)."""
        # Create playback timer if needed
        if self.playback_timer is None:
            self.playback_timer = QTimer(self)
            self.playback_timer.timeout.connect(self._advance_frame)

        # Calculate frame interval (60 frames/sec NTSC timing)
        frames_per_second = 60
        ms_per_frame = int(1000 / frames_per_second)
        self.playback_timer.start(ms_per_frame)

        self.is_playing = True
        self.btn_frame_play.setEnabled(False)
        self.btn_frame_pause.setEnabled(True)
        self.btn_frame_stop.setEnabled(True)
        self.statusBar().showMessage("Playing...", 0)

    def _on_frame_pause(self) -> None:
        """Pause frame playback."""
        if self.playback_timer:
            self.playback_timer.stop()

        self.is_playing = False
        self.btn_frame_play.setEnabled(True)
        self.btn_frame_pause.setEnabled(False)
        self.statusBar().showMessage(f"Paused at frame {self.current_frame}", 0)

    def _on_frame_stop(self) -> None:
        """Stop frame playback and reset."""
        if self.playback_timer:
            self.playback_timer.stop()

        # Stop audio
        if self.audio_stream:
            self.audio_stream.stop()

        self.is_playing = False
        self.current_frame = 0

        # Clear playback position highlight
        self.timeline.set_playback_position(-1)

        # Reset PSG state
        self.current_state = PSGState()
        self._update_register_display()

        self.btn_frame_play.setEnabled(True)
        self.btn_frame_pause.setEnabled(False)
        self.btn_frame_stop.setEnabled(False)
        self.statusBar().showMessage("Stopped")

    def _on_frame_loop_toggled(self, checked: bool) -> None:
        """Toggle loop mode."""
        self.playback_loop = checked

    def _advance_frame(self) -> None:
        """Advance to next frame and update PSG state."""
        # Apply frame data to PSG state for each channel
        for channel_id, frames in self.timeline_data.items():
            if self.current_frame in frames:
                data = frames[self.current_frame]

                if channel_id == "A":
                    self._apply_frame_to_channel(self.current_state.channel_a, data)
                elif channel_id == "B":
                    self._apply_frame_to_channel(self.current_state.channel_b, data)
                elif channel_id == "C":
                    self._apply_frame_to_channel(self.current_state.channel_c, data)
                elif channel_id == "N":
                    # Apply noise period
                    if data.get("volume") is not None:
                        # Use volume as noise period for noise track
                        self.current_state.noise_period = data.get("volume", 1)

        # Update register display
        self._update_register_display()

        # Highlight current playback position
        self.timeline.set_playback_position(self.current_frame)

        # Advance frame counter
        self.current_frame += 1

        # Check for end of timeline
        max_frame = max(
            (max(frames.keys()) if frames else 0 for frames in self.timeline_data.values()),
            default=0,
        )

        if self.current_frame > max_frame:
            if self.playback_loop:
                self.current_frame = 0
            else:
                self._on_frame_stop()

    def _apply_frame_to_channel(self, channel, data: dict) -> None:
        """Apply frame data to a PSG channel.

        Args:
            channel: PSGChannel to update
            data: Frame data dict
        """
        if data.get("frequency") is not None:
            channel.frequency = data["frequency"]
        if data.get("volume") is not None:
            channel.volume = data["volume"]
        if data.get("tone_enabled") is not None:
            channel.tone_enabled = data["tone_enabled"]
        if data.get("noise_enabled") is not None:
            channel.noise_enabled = data["noise_enabled"]

    def _on_noise_slider_changed(self, value: int) -> None:
        """Noise period slider changed - update text input and PSG state."""
        self.current_state.noise_period = value
        self.noise_input.blockSignals(True)
        self.noise_input.setText(str(value))
        self.noise_input.blockSignals(False)
        if value == 0:
            self.noise_label.setText("Period: 0 (OFF)")
        else:
            # Show period value and approximate frequency
            from tellijase.psg.utils import CLOCK_HZ

            freq = CLOCK_HZ / (32.0 * value) if value > 0 else 0
            self.noise_label.setText(f"Period: {value} (~{freq:.0f} Hz)")
        self._update_register_display()

    def _on_noise_input_changed(self) -> None:
        """Noise period text input changed - update slider and PSG state."""
        try:
            value = int(self.noise_input.text())
            # Clamp to valid range (0-31)
            value = max(0, min(31, value))
            self.noise_slider.blockSignals(True)
            self.noise_slider.setValue(value)
            self.noise_slider.blockSignals(False)
            self.noise_input.setText(str(value))  # Show clamped value
            self.current_state.noise_period = value
            if value == 0:
                self.noise_label.setText("Period: 0 (OFF)")
            else:
                from tellijase.psg.utils import CLOCK_HZ

                freq = CLOCK_HZ / (32.0 * value) if value > 0 else 0
                self.noise_label.setText(f"Period: {value} (~{freq:.0f} Hz)")
            self._update_register_display()
        except ValueError:
            # Invalid input - restore from slider
            self.noise_input.setText(str(self.noise_slider.value()))

    def _update_channel_param(self, channel, param_name: str, value) -> None:
        """Update a channel parameter and refresh register display.

        Args:
            channel: PSGChannel to update
            param_name: Name of the parameter to set
            value: New value
        """
        setattr(channel, param_name, value)
        self._update_register_display()

    def _update_register_display(self) -> None:
        """Update the register value display with current PSG state."""
        from tellijase.psg.utils import period_to_frequency

        regs = self.current_state.to_registers()

        # LEFT: Input (raw register values)
        input_lines = []
        input_lines.append("Tone Periods:")
        input_lines.append(f"  A: R0=${regs.get('R0', 0):02X} R1=${regs.get('R1', 0):02X}")
        input_lines.append(f"  B: R2=${regs.get('R2', 0):02X} R3=${regs.get('R3', 0):02X}")
        input_lines.append(f"  C: R4=${regs.get('R4', 0):02X} R5=${regs.get('R5', 0):02X}")
        input_lines.append("")
        input_lines.append(f"Noise: R6=${regs.get('R6', 0):02X}")
        input_lines.append(f"Mixer: R7=${regs.get('R7', 0xFF):02X}")
        input_lines.append("")
        input_lines.append("Volumes:")
        input_lines.append(f"  A: R10=${regs.get('R10', 0):02X}")
        input_lines.append(f"  B: R11=${regs.get('R11', 0):02X}")
        input_lines.append(f"  C: R12=${regs.get('R12', 0):02X}")
        input_lines.append("")
        input_lines.append("Envelope:")
        input_lines.append(f"  R13=${regs.get('R13', 0):02X} R14=${regs.get('R14', 0):02X}")
        input_lines.append(f"  R15=${regs.get('R15', 0):02X}")

        self.register_input_display.setText("\n".join(input_lines))

        # RIGHT: Output (decoded values)
        output_lines = []

        # Decode mixer
        r7 = regs.get("R7", 0xFF)

        # Channel A
        period_a = (regs.get("R1", 0) << 8) | regs.get("R0", 0)
        freq_a = period_to_frequency(period_a)
        vol_a = regs.get("R10", 0) & 0x0F
        tone_a = "Tone" if not (r7 & 0x01) else ""
        noise_a = "Noise" if not (r7 & 0x08) else ""
        mix_a = "+".join(filter(None, [tone_a, noise_a])) or "NONE"

        output_lines.append(f"Channel A: {freq_a:6.1f} Hz (period={period_a})")
        output_lines.append(f"  Volume: {vol_a:2d}/15")
        output_lines.append(f"  Mix: {mix_a}")
        output_lines.append("")

        # Channel B
        period_b = (regs.get("R3", 0) << 8) | regs.get("R2", 0)
        freq_b = period_to_frequency(period_b)
        vol_b = regs.get("R11", 0) & 0x0F
        tone_b = "Tone" if not (r7 & 0x02) else ""
        noise_b = "Noise" if not (r7 & 0x10) else ""
        mix_b = "+".join(filter(None, [tone_b, noise_b])) or "NONE"

        output_lines.append(f"Channel B: {freq_b:6.1f} Hz (period={period_b})")
        output_lines.append(f"  Volume: {vol_b:2d}/15")
        output_lines.append(f"  Mix: {mix_b}")
        output_lines.append("")

        # Channel C
        period_c = (regs.get("R5", 0) << 8) | regs.get("R4", 0)
        freq_c = period_to_frequency(period_c)
        vol_c = regs.get("R12", 0) & 0x0F
        tone_c = "Tone" if not (r7 & 0x04) else ""
        noise_c = "Noise" if not (r7 & 0x20) else ""
        mix_c = "+".join(filter(None, [tone_c, noise_c])) or "NONE"

        output_lines.append(f"Channel C: {freq_c:6.1f} Hz (period={period_c})")
        output_lines.append(f"  Volume: {vol_c:2d}/15")
        output_lines.append(f"  Mix: {mix_c}")
        output_lines.append("")

        # Noise
        noise_period = regs.get("R6", 0)
        if noise_period > 0:
            noise_freq = period_to_frequency(noise_period)
            output_lines.append(f"Noise: {noise_freq:6.1f} Hz (period={noise_period})")
        else:
            output_lines.append("Noise: OFF")
        output_lines.append("")

        # Mixer decode (R7 in binary for clarity)
        output_lines.append(f"Mixer R7: {r7:08b}b")
        output_lines.append("")

        # Envelope (placeholder for future implementation)
        # env_period = (regs.get('R14', 0) << 8) | regs.get('R13', 0)
        # env_shape = regs.get('R15', 0)
        output_lines.append("Envelope: Not implemented")

        self.register_output_display.setText("\n".join(output_lines))

    def _on_play_audio(self) -> None:
        """Start real-time audio playback with automatic backend fallback."""
        if not self.audio_available:
            self._warn_audio_missing()
            return

        # Try current backend
        if self.audio_stream and self.audio_stream.start():
            self.btn_play.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self.statusBar().showMessage(f"Playing with {self.audio_backend}…", 3000)
            return

        # Current backend failed - try fallback to pygame
        if self.audio_backend == "sounddevice" and PYGAME_AVAILABLE:
            logger.warning("sounddevice failed to start, falling back to pygame")
            try:
                self.audio_stream = PygamePSGPlayer(self.current_state)
                self.audio_backend = "pygame"
                if self.audio_stream.start():
                    self.btn_play.setEnabled(False)
                    self.btn_stop.setEnabled(True)
                    self.jam_status_label.setText(f"Audio: {self.audio_backend} (fallback)")
                    self.jam_status_label.setStyleSheet("color: orange;")
                    self.statusBar().showMessage(
                        f"Playing with {self.audio_backend} (fallback)…", 3000
                    )
                    return
            except Exception as e:
                logger.error(f"pygame fallback failed: {e}")

        # All backends failed
        QMessageBox.warning(
            self,
            "Playback Failed",
            f"Failed to start audio with {self.audio_backend}.\n\n"
            "Check console for errors. Audio may not be available in this environment.",
        )

    def _on_stop_audio(self) -> None:
        """Stop audio playback."""
        if self.audio_stream:
            self.audio_stream.stop()
            self.btn_play.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.statusBar().showMessage("Playback stopped", 2000)

    def _warn_audio_missing(self) -> None:
        """Show warning popup when audio is unavailable."""
        QMessageBox.warning(
            self,
            "Audio Unavailable",
            "telliJASE audio playback is disabled.\n\n"
            "sounddevice library not found. Install with:\n\n"
            "  pip install sounddevice\n\n"
            "On WSL/Linux, you may also need:\n"
            "  sudo apt-get install libportaudio2\n\n"
            "You can still edit and save PSG settings without audio preview.",
        )

    def _update_title(self) -> None:
        name = self.project.meta.name or "Untitled"
        if self.current_file:
            self.setWindowTitle(f"telliJASE - {self.current_file.name}")
        else:
            self.setWindowTitle(f"telliJASE - {name}")


def run(app: Optional[QApplication] = None) -> int:
    """Launch the PySide6 event loop."""

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(name)s: %(message)s",
    )

    should_cleanup = False
    if app is None:
        app = QApplication(sys.argv)
        should_cleanup = True

    window = MainWindow()
    window.show()
    exit_code = app.exec()

    if should_cleanup:
        del app

    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
