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
    QLineEdit,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QSlider,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from tellijase.audio.stream import LivePSGStream, SOUNDDEVICE_AVAILABLE
from tellijase.audio.pygame_player import PygamePSGPlayer, PYGAME_AVAILABLE
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

        # Noise period control (shared across all channels)
        noise_group = QWidget()
        noise_layout = QVBoxLayout(noise_group)
        noise_layout.setContentsMargins(20, 10, 20, 10)

        self.noise_label = QLabel("Noise Period: 0 (disabled)")
        noise_layout.addWidget(self.noise_label)

        # Horizontal layout with slider and text input
        noise_row = QHBoxLayout()
        self.noise_slider = QSlider(Qt.Horizontal)
        self.noise_slider.setRange(0, 31)  # R6 is 5 bits (0-31)
        self.noise_slider.setValue(0)
        self.noise_slider.valueChanged.connect(self._on_noise_slider_changed)

        self.noise_input = QLineEdit()
        self.noise_input.setMaximumWidth(70)
        self.noise_input.setText("0")
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

        if not self.audio_available:
            self.btn_play.setEnabled(False)
            self.btn_stop.setEnabled(False)
            self.jam_status_label.setText(
                f"⚠️ Audio unavailable (no backend found)"
            )
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

    def _on_noise_slider_changed(self, value: int) -> None:
        """Noise period slider changed - update text input and PSG state."""
        self.current_state.noise_period = value
        self.noise_input.blockSignals(True)
        self.noise_input.setText(str(value))
        self.noise_input.blockSignals(False)
        if value == 0:
            self.noise_label.setText("Noise Period: 0 (disabled)")
        else:
            # Show period value and approximate frequency
            from tellijase.psg.utils import CLOCK_HZ
            freq = CLOCK_HZ / (32.0 * value) if value > 0 else 0
            self.noise_label.setText(f"Noise Period: {value} (~{freq:.0f} Hz)")
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
                self.noise_label.setText("Noise Period: 0 (disabled)")
            else:
                from tellijase.psg.utils import CLOCK_HZ
                freq = CLOCK_HZ / (32.0 * value) if value > 0 else 0
                self.noise_label.setText(f"Noise Period: {value} (~{freq:.0f} Hz)")
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
        r7 = regs.get('R7', 0xFF)

        # Channel A
        period_a = (regs.get('R1', 0) << 8) | regs.get('R0', 0)
        freq_a = period_to_frequency(period_a)
        vol_a = regs.get('R10', 0) & 0x0F
        tone_a = "Tone" if not (r7 & 0x01) else ""
        noise_a = "Noise" if not (r7 & 0x08) else ""
        mix_a = "+".join(filter(None, [tone_a, noise_a])) or "MUTE"

        output_lines.append(f"Channel A: {freq_a:6.1f} Hz (period={period_a})")
        output_lines.append(f"  Volume: {vol_a:2d}/15")
        output_lines.append(f"  Mix: {mix_a}")
        output_lines.append("")

        # Channel B
        period_b = (regs.get('R3', 0) << 8) | regs.get('R2', 0)
        freq_b = period_to_frequency(period_b)
        vol_b = regs.get('R11', 0) & 0x0F
        tone_b = "Tone" if not (r7 & 0x02) else ""
        noise_b = "Noise" if not (r7 & 0x10) else ""
        mix_b = "+".join(filter(None, [tone_b, noise_b])) or "MUTE"

        output_lines.append(f"Channel B: {freq_b:6.1f} Hz (period={period_b})")
        output_lines.append(f"  Volume: {vol_b:2d}/15")
        output_lines.append(f"  Mix: {mix_b}")
        output_lines.append("")

        # Channel C
        period_c = (regs.get('R5', 0) << 8) | regs.get('R4', 0)
        freq_c = period_to_frequency(period_c)
        vol_c = regs.get('R12', 0) & 0x0F
        tone_c = "Tone" if not (r7 & 0x04) else ""
        noise_c = "Noise" if not (r7 & 0x20) else ""
        mix_c = "+".join(filter(None, [tone_c, noise_c])) or "MUTE"

        output_lines.append(f"Channel C: {freq_c:6.1f} Hz (period={period_c})")
        output_lines.append(f"  Volume: {vol_c:2d}/15")
        output_lines.append(f"  Mix: {mix_c}")
        output_lines.append("")

        # Noise
        noise_period = regs.get('R6', 0)
        if noise_period > 0:
            noise_freq = period_to_frequency(noise_period)
            output_lines.append(f"Noise: {noise_freq:6.1f} Hz (period={noise_period})")
        else:
            output_lines.append("Noise: MUTE")
        output_lines.append("")

        # Mixer decode (R7 in binary for clarity)
        output_lines.append(f"Mixer R7: {r7:08b}b")
        output_lines.append("")

        # Envelope (placeholder for future implementation)
        env_period = (regs.get('R14', 0) << 8) | regs.get('R13', 0)
        env_shape = regs.get('R15', 0)
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
                    self.statusBar().showMessage(f"Playing with {self.audio_backend} (fallback)…", 3000)
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
