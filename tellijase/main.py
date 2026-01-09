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
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from tellijase.audio.stream import LivePSGStream, SOUNDDEVICE_AVAILABLE
from tellijase.models import JAMSnapshot, PSGState
from tellijase.storage import JamSession, Project, load_project, new_project, save_project
from tellijase.ui.jam_controls import ChannelControl

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """telliJASE main window with JAM + FRAME placeholders."""

    def __init__(self) -> None:
        super().__init__()

        # Models (domain layer - pure data)
        self.project: Project = new_project()
        self.current_state = PSGState()  # Live JAM state
        self.current_file: Optional[Path] = None

        # UI widgets
        self.channel_controls: list[ChannelControl] = []

        # Audio
        self.audio_stream: Optional[LivePSGStream] = None
        self.audio_available = SOUNDDEVICE_AVAILABLE

        if self.audio_available:
            try:
                self.audio_stream = LivePSGStream(self.current_state)
                logger.info("Audio stream initialized")
            except Exception as e:
                logger.error(f"Failed to initialize audio: {e}")
                self.audio_available = False
                self.audio_stream = None

        self.setMinimumSize(1280, 768)
        self.resize(1600, 900)

        self._create_actions()
        self._create_menus()
        self._create_toolbar()
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
        self.action_new = self._make_action("&New Project", "Ctrl+N", self.new_project)
        self.action_open = self._make_action("&Open Project…", "Ctrl+O", self.open_project)
        self.action_save = self._make_action("&Save Project", "Ctrl+S", self.save_project)
        self.action_save_as = self._make_action("Save Project &As…", "Ctrl+Shift+S", self.save_project_as)
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

        self.setMenuBar(menubar)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.addAction(self.action_new)
        toolbar.addAction(self.action_open)
        toolbar.addAction(self.action_save)
        self.addToolBar(toolbar)

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

        button_row = QHBoxLayout()
        self.btn_new_session = QPushButton("New JAM Session")
        self.btn_snapshot = QPushButton("Snapshot Current State")
        self.btn_play = QPushButton("Play Preview")
        self.btn_stop = QPushButton("Stop")
        button_row.addWidget(self.btn_new_session)
        button_row.addWidget(self.btn_snapshot)
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

        self.jam_status_label = QLabel("Shadow registers ready.")
        layout.addWidget(self.jam_status_label)

        layout.addStretch()
        return widget

    def _build_frame_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("<h3>FRAME Sequencer</h3>"))
        layout.addWidget(QLabel("Keyframe timeline reminiscent of telliGRAM's animation editor."))

        transport = QHBoxLayout()
        for label in ("Play", "Pause", "Stop", "Loop"):
            button = QPushButton(label)
            button.setEnabled(False)
            transport.addWidget(button)
        transport.addStretch()
        layout.addLayout(transport)

        self.timeline_placeholder = QLabel("Timeline grid placeholder based on For-Codex.png")
        self.timeline_placeholder.setAlignment(Qt.AlignCenter)
        self.timeline_placeholder.setStyleSheet("border: 1px dashed #888; padding: 40px;")
        layout.addWidget(self.timeline_placeholder, stretch=1)
        return widget

    def _connect_signals(self) -> None:
        """Connect UI signals to model updates - clean model-view separation."""
        self.btn_new_session.clicked.connect(self._on_new_session)
        self.btn_snapshot.clicked.connect(self._on_snapshot)
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

            # Wire signals to model (direct field assignment)
            control.frequency_changed.connect(
                lambda freq, ch=channel: setattr(ch, "frequency", freq)
            )
            control.volume_changed.connect(
                lambda vol, ch=channel: setattr(ch, "volume", vol)
            )
            control.tone_enabled_changed.connect(
                lambda enabled, ch=channel: setattr(ch, "tone_enabled", enabled)
            )
            control.noise_enabled_changed.connect(
                lambda enabled, ch=channel: setattr(ch, "noise_enabled", enabled)
            )

    def _initialize_jam_controls(self) -> None:
        """Initialize JAM controls with current model state."""
        for control in self.channel_controls:
            control.emit_state()

        if not self.audio_available:
            self.btn_play.setEnabled(False)
            self.btn_stop.setEnabled(False)
            self.jam_status_label.setText(
                "⚠️ Audio unavailable (sounddevice not installed)"
            )
            self.jam_status_label.setStyleSheet("color: orange; font-weight: bold;")

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

    # JAM Mode Callbacks ----------------------------------------------
    def _on_new_session(self) -> None:
        """Create a new JAM session snapshot."""
        new_id = f"jam-{len(self.project.jam_sessions) + 1}"
        session = JamSession(
            id=new_id,
            name=f"Session {len(self.project.jam_sessions) + 1}",
            registers=self.current_state.to_registers(),
        )
        self.project.jam_sessions.append(session)
        self.project.touch()
        self.statusBar().showMessage(f"Added {session.name}", 3000)

    def _on_snapshot(self) -> None:
        """Save current PSG state to the active session."""
        if not self.project.jam_sessions:
            self._on_new_session()
            return
        session = self.project.jam_sessions[-1]
        session.registers = self.current_state.to_registers()
        session.updated = datetime.utcnow().isoformat()
        self.project.touch()
        self.statusBar().showMessage(f"Snapshot saved to {session.name}", 3000)

    def _on_play_audio(self) -> None:
        """Start real-time audio playback."""
        if not self.audio_available:
            self._warn_audio_missing()
            return

        if self.audio_stream and self.audio_stream.start():
            self.btn_play.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self.statusBar().showMessage("Playing (move sliders to hear changes)…", 3000)
        else:
            QMessageBox.warning(
                self,
                "Playback Failed",
                "Failed to start audio stream. Check console for errors.",
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
