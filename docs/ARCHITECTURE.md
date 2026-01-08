# telliJASE Architecture Design

## Vision

A **live PSG synthesizer** for Intellivision game development. Move a slider, hear the sound change instantly. Jam to find sounds, save snapshots, export to IntyBASIC.

**Design Philosophy:** Match telliGRAM's clean architecture:
- Testable domain models (no Qt dependencies)
- Signal/slot for UI communication
- Phase-based development
- Type-safe, not stringly-typed

---

## System Overview

```
┌──────────────────────────────────────────────────────────────┐
│                        MainWindow (Qt)                        │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────────┐   │
│  │ JAM Tab    │  │ FRAME Tab  │  │  File/Project Menu   │   │
│  │(live play) │  │(sequencer) │  │  (New/Open/Save)     │   │
│  └─────┬──────┘  └────────────┘  └──────────────────────┘   │
│        │                                                      │
│   signals (high-level: freq_hz, volume)                      │
│        │                                                      │
│        ▼                                                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              PSGState (domain model)                 │    │
│  │  - channel_a/b/c: PSGChannel dataclasses            │    │
│  │  - noise_period, envelope_period                    │    │
│  │  - to_registers() → dict[str, int]                  │    │
│  └──────────────────┬──────────────────────────────────┘    │
└───────────────────────┼──────────────────────────────────────┘
                        │
                        │ snapshot() every ~20ms
                        ▼
              ┌──────────────────────┐
              │   Audio Synthesis    │
              │   (sounddevice)      │
              │  - Callback thread   │
              │  - Phase accumulators│
              │  - Correct R7 mixing │
              └──────────────────────┘
                        │
                        ▼
                    🔊 Output
```

---

## Layer 1: Domain Models (Pure Python, Testable)

### `models/psg_channel.py`

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class PSGChannel:
    """Domain model for one AY-3-8914 channel."""

    # High-level parameters (user-facing)
    frequency: float = 440.0        # Hz
    volume: int = 12                # 0-15
    tone_enabled: bool = True       # R7 mixer bit
    noise_enabled: bool = False     # R7 mixer bit
    envelope_mode: bool = False     # Use envelope instead of fixed volume

    def to_registers(self, reg_offset: int) -> dict[str, int]:
        """Convert to AY-3-8914 register values.

        Args:
            reg_offset: 0 for channel A, 2 for B, 4 for C

        Returns:
            Register dict with keys like 'R0', 'R1', 'R8'
        """
        period = frequency_to_period(self.frequency)
        fine_reg = f"R{reg_offset}"
        coarse_reg = f"R{reg_offset + 1}"
        vol_reg = f"R{8 + reg_offset // 2}"

        volume_byte = self.volume & 0x0F
        if self.envelope_mode:
            volume_byte |= 0x10  # Set M bit

        return {
            fine_reg: period & 0xFF,
            coarse_reg: (period >> 8) & 0x0F,
            vol_reg: volume_byte,
        }

    def validate(self) -> None:
        """Raise ValueError if parameters are out of range."""
        if not (55 <= self.frequency <= 20000):
            raise ValueError(f"Frequency {self.frequency} out of range")
        if not (0 <= self.volume <= 15):
            raise ValueError(f"Volume {self.volume} must be 0-15")
```

### `models/psg_state.py`

```python
from dataclasses import dataclass, field, replace
from typing import Dict

@dataclass
class PSGState:
    """Complete AY-3-8914 state - the single source of truth."""

    channel_a: PSGChannel = field(default_factory=PSGChannel)
    channel_b: PSGChannel = field(default_factory=PSGChannel)
    channel_c: PSGChannel = field(default_factory=PSGChannel)

    noise_period: int = 0           # R6 (0-31)
    envelope_period: int = 0        # R11/R12 (0-65535)
    envelope_shape: int = 0         # R13 (0-15)

    def to_registers(self) -> Dict[str, int]:
        """Flatten to R0-R13 for audio synthesis."""
        regs = {}

        # Channels
        regs.update(self.channel_a.to_registers(0))
        regs.update(self.channel_b.to_registers(2))
        regs.update(self.channel_c.to_registers(4))

        # R7 mixer control (inverted logic: 0=enable, 1=disable)
        r7 = 0xFF  # Start with all disabled
        if self.channel_a.tone_enabled:
            r7 &= ~0x01
        if self.channel_b.tone_enabled:
            r7 &= ~0x02
        if self.channel_c.tone_enabled:
            r7 &= ~0x04
        if self.channel_a.noise_enabled:
            r7 &= ~0x08
        if self.channel_b.noise_enabled:
            r7 &= ~0x10
        if self.channel_c.noise_enabled:
            r7 &= ~0x20
        regs["R7"] = r7

        # Noise
        regs["R6"] = self.noise_period & 0x1F

        # Envelope
        regs["R11"] = self.envelope_period & 0xFF
        regs["R12"] = (self.envelope_period >> 8) & 0xFF
        regs["R13"] = self.envelope_shape & 0x0F

        return regs

    def snapshot(self) -> "PSGState":
        """Thread-safe immutable copy for audio thread."""
        return replace(
            self,
            channel_a=replace(self.channel_a),
            channel_b=replace(self.channel_b),
            channel_c=replace(self.channel_c),
        )

    @classmethod
    def from_registers(cls, registers: Dict[str, int]) -> "PSGState":
        """Deserialize from register dict (for loading projects)."""
        # ... inverse of to_registers()
```

### `models/project.py`

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import List

@dataclass
class JAMSnapshot:
    """A saved PSG state from JAM mode."""
    name: str
    state: PSGState
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    notes: str = ""  # User annotations

@dataclass
class Project:
    """telliJASE project - like telliGRAM's Project model."""
    name: str = "Untitled"
    created: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    modified: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    jam_snapshots: List[JAMSnapshot] = field(default_factory=list)
    # Future: frame_timeline, patterns, etc.

    def touch(self) -> None:
        """Update modification timestamp."""
        self.modified = datetime.utcnow().isoformat()
```

**Why this works:**
- ✅ Zero Qt dependencies → fully unit testable
- ✅ Type-safe: `channel.frequency` not `registers['R0']`
- ✅ Serialization-ready: dataclasses → JSON
- ✅ Matches telliGRAM: same Project + dataclass pattern

---

## Layer 2: Audio Synthesis (sounddevice + numpy)

### `audio/synthesizer.py`

```python
import numpy as np
from ..models import PSGState
from .utils import period_to_frequency, frequency_to_period, CLOCK_HZ

class PSGSynthesizer:
    """Generates PCM audio from PSGState - pure numpy, no Qt."""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate

        # Phase accumulators for continuity (no clicks)
        self.phase_a = 0.0
        self.phase_b = 0.0
        self.phase_c = 0.0
        self.noise_phase = 0.0

        # Noise LFSR state
        self.lfsr = 1  # 17-bit shift register

    def render_buffer(self, num_samples: int, state: PSGState) -> np.ndarray:
        """Generate mono PCM samples from current PSG state.

        Returns:
            float32 array of samples in range [-1.0, 1.0]
        """
        regs = state.to_registers()
        r7 = regs.get("R7", 0xFF)

        # Generate shared noise waveform
        noise = self._generate_noise(num_samples, regs.get("R6", 0))

        # Generate and mix channels
        channels = [
            (self.phase_a, 0, "R0", "R1", "R8", 0x01, 0x08),  # A
            (self.phase_b, 1, "R2", "R3", "R9", 0x02, 0x10),  # B
            (self.phase_c, 2, "R4", "R5", "R10", 0x04, 0x20), # C
        ]

        mix = np.zeros(num_samples, dtype=np.float32)

        for phase_attr, idx, fine_r, coarse_r, vol_r, tone_bit, noise_bit in channels:
            # Check mixer enables
            tone_enabled = not (r7 & tone_bit)
            noise_enabled = not (r7 & noise_bit)

            if not tone_enabled and not noise_enabled:
                continue  # Channel silent

            # Generate channel signal (tone AND/OR noise)
            channel_signal = np.zeros(num_samples, dtype=np.float32)

            if tone_enabled:
                period = self._read_period(regs, fine_r, coarse_r)
                freq = period_to_frequency(period)
                tone, new_phase = self._generate_tone(num_samples, freq, phase_attr)
                channel_signal += tone
                # Update phase accumulator
                if idx == 0:
                    self.phase_a = new_phase
                elif idx == 1:
                    self.phase_b = new_phase
                else:
                    self.phase_c = new_phase

            if noise_enabled:
                channel_signal += noise

            # Apply volume to MIXED signal
            volume = regs.get(vol_r, 0) & 0x0F
            amplitude = volume / 15.0
            mix += channel_signal * amplitude

        # Normalize and clamp
        max_val = np.max(np.abs(mix))
        if max_val > 0:
            mix = mix / max_val

        return np.clip(mix, -1.0, 1.0).astype(np.float32)

    def _generate_tone(self, num_samples: int, freq: float, phase: float) -> tuple[np.ndarray, float]:
        """Generate square wave with phase continuity."""
        if freq <= 0:
            return np.zeros(num_samples), phase

        phase_increment = freq / self.sample_rate
        phases = np.arange(num_samples) * phase_increment + phase
        wave = np.where((phases % 1.0) < 0.5, 1.0, -1.0).astype(np.float32)
        new_phase = (phases[-1] + phase_increment) % 1.0
        return wave, new_phase

    def _generate_noise(self, num_samples: int, period: int) -> np.ndarray:
        """Generate pseudo-random noise using LFSR."""
        if period == 0:
            return np.zeros(num_samples, dtype=np.float32)

        # Simplified: use numpy random for now
        # TODO: Implement proper 17-bit LFSR for accuracy
        noise_freq = CLOCK_HZ / (16.0 * period) if period > 0 else 0
        samples_per_bit = max(1, int(self.sample_rate / noise_freq))
        noise = np.random.default_rng(seed=self.lfsr).uniform(-1.0, 1.0, num_samples)
        self.lfsr = (self.lfsr + 1) % 0x1FFFF  # Cycle LFSR state
        return noise.astype(np.float32)

    @staticmethod
    def _read_period(regs: dict, fine_r: str, coarse_r: str) -> int:
        fine = regs.get(fine_r, 0)
        coarse = regs.get(coarse_r, 0) & 0x0F
        return max(1, (coarse << 8) | fine)
```

### `audio/stream.py`

```python
import sounddevice as sd
from typing import Optional
from ..models import PSGState
from .synthesizer import PSGSynthesizer

class LivePSGStream:
    """Real-time audio streaming using sounddevice."""

    def __init__(self, psg_state: PSGState, sample_rate: int = 44100):
        self.psg_state = psg_state
        self.sample_rate = sample_rate
        self.synth = PSGSynthesizer(sample_rate)
        self.stream: Optional[sd.OutputStream] = None

    def _callback(self, outdata, frames, time, status):
        """Called by audio thread - generate samples on demand."""
        if status:
            print(f"Audio underrun: {status}")

        # Thread-safe snapshot of current state
        state = self.psg_state.snapshot()

        # Generate samples with phase continuity
        samples = self.synth.render_buffer(frames, state)

        # Write to output (sounddevice expects Nx1 for mono)
        outdata[:] = samples.reshape(-1, 1)

    def start(self) -> None:
        """Start continuous audio playback."""
        if self.stream is None:
            self.stream = sd.OutputStream(
                channels=1,
                samplerate=self.sample_rate,
                callback=self._callback,
                blocksize=2048,  # ~46ms latency @ 44.1kHz
            )
        self.stream.start()

    def stop(self) -> None:
        """Stop audio playback."""
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
```

**Why sounddevice:**
- ✅ WSL-compatible (PortAudio → PulseAudio)
- ✅ Real-time callback API (not one-shot playback)
- ✅ Lightweight (not a game engine like pygame)
- ✅ Numpy-native (perfect for our synthesis)

---

## Layer 3: UI (PySide6)

### `ui/channel_widget.py`

```python
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QSlider, QLabel, QCheckBox

class ChannelWidget(QGroupBox):
    """UI for one PSG channel - emits high-level signals."""

    # High-level signals (domain concepts, not registers)
    frequency_changed = Signal(float)
    volume_changed = Signal(int)
    tone_enabled_changed = Signal(bool)
    noise_enabled_changed = Signal(bool)

    def __init__(self, channel_name: str):
        super().__init__(f"Channel {channel_name}")

        layout = QVBoxLayout(self)

        # Frequency
        self.freq_label = QLabel("Frequency: 440 Hz")
        self.freq_slider = QSlider(Qt.Horizontal)
        self.freq_slider.setRange(55, 2000)
        self.freq_slider.setValue(440)
        self.freq_slider.valueChanged.connect(self._on_freq_changed)
        layout.addWidget(self.freq_label)
        layout.addWidget(self.freq_slider)

        # Volume
        self.vol_label = QLabel("Volume: 12")
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 15)
        self.vol_slider.setValue(12)
        self.vol_slider.valueChanged.connect(self._on_vol_changed)
        layout.addWidget(self.vol_label)
        layout.addWidget(self.vol_slider)

        # Mixer checkboxes
        self.tone_check = QCheckBox("Tone")
        self.tone_check.setChecked(True)
        self.tone_check.toggled.connect(self.tone_enabled_changed)
        layout.addWidget(self.tone_check)

        self.noise_check = QCheckBox("Noise")
        self.noise_check.setChecked(False)
        self.noise_check.toggled.connect(self.noise_enabled_changed)
        layout.addWidget(self.noise_check)

        layout.addStretch()

    def _on_freq_changed(self, value: int) -> None:
        self.freq_label.setText(f"Frequency: {value} Hz")
        self.frequency_changed.emit(float(value))

    def _on_vol_changed(self, value: int) -> None:
        self.vol_label.setText(f"Volume: {value}")
        self.volume_changed.emit(value)

    def set_state(self, channel: PSGChannel) -> None:
        """Update UI from model (for loading projects)."""
        self.freq_slider.setValue(int(channel.frequency))
        self.vol_slider.setValue(channel.volume)
        self.tone_check.setChecked(channel.tone_enabled)
        self.noise_check.setChecked(channel.noise_enabled)
```

### `app.py` (MainWindow orchestration)

```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Models
        self.project = Project()
        self.current_state = PSGState()  # Live JAM state

        # Audio
        try:
            import sounddevice as sd
            self.audio_stream = LivePSGStream(self.current_state)
            self.audio_available = True
        except (ImportError, OSError):
            self.audio_available = False
            self.audio_stream = None

        # UI setup
        self._create_ui()
        self._connect_signals()

        # Warn if audio missing (after window shows)
        if not self.audio_available:
            QTimer.singleShot(100, self._warn_audio_missing)

    def _connect_signals(self):
        """Connect high-level UI signals to model updates."""
        self.channel_a_widget.frequency_changed.connect(
            lambda f: setattr(self.current_state.channel_a, 'frequency', f)
        )
        self.channel_a_widget.volume_changed.connect(
            lambda v: setattr(self.current_state.channel_a, 'volume', v)
        )
        self.channel_a_widget.tone_enabled_changed.connect(
            lambda e: setattr(self.current_state.channel_a, 'tone_enabled', e)
        )
        # ... same for B and C

    def _on_play_jam(self):
        if self.audio_available:
            self.audio_stream.start()
        else:
            self._warn_audio_missing()

    def _on_stop_jam(self):
        if self.audio_stream:
            self.audio_stream.stop()

    def _warn_audio_missing(self):
        QMessageBox.warning(
            self,
            "Audio Unavailable",
            "sounddevice not found. Install with:\n\n"
            "  pip install sounddevice\n\n"
            "You can still edit and save PSG settings.",
        )
```

---

## Threading Model

**Simple and safe:**

```
UI Thread (Qt event loop)
  │
  ├─ Slider move → self.current_state.channel_a.frequency = 880
  │  (just a dataclass field assignment)
  │
  └─ No locks needed (Python assigns are atomic for simple types)

Audio Thread (sounddevice callback)
  │
  └─ state = self.current_state.snapshot()  # dataclass copy
     ↓
     synth.render_buffer(frames, state)
     ↓
     return PCM samples
```

**Why no locks:**
- UI writes simple fields (floats, ints, bools)
- Audio thread takes immutable snapshot (dataclass `replace()`)
- Worst case: one buffer has mixed old/new params (20ms, imperceptible)

---

## Development Phases (telliGRAM-style)

### Phase 1: Core Models ✅
- PSGChannel, PSGState, Project dataclasses
- Unit tests (no Qt)
- JSON serialization

### Phase 2: Basic Synthesis 🔄
- PSGSynthesizer with correct R7 mixing
- Unit tests (generate buffers, check waveforms)
- Test tone+noise mixing

### Phase 3: Live JAM UI
- ChannelWidget with sliders
- sounddevice streaming
- Real-time parameter changes

### Phase 4: Project I/O
- Save/load .tellijase files
- JAM snapshot management
- Export to IntyBASIC format

### Phase 5: FRAME Sequencer
- Timeline editor (like telliGRAM animations)
- Keyframe interpolation
- Playback controls

---

## File Structure

```
tellijase/
  models/
    __init__.py
    psg_channel.py      # PSGChannel dataclass
    psg_state.py        # PSGState, register conversion
    project.py          # Project, JAMSnapshot
  audio/
    __init__.py
    synthesizer.py      # PSGSynthesizer (numpy)
    stream.py           # LivePSGStream (sounddevice)
    utils.py            # freq conversions, CLOCK_HZ
  ui/
    __init__.py
    channel_widget.py   # ChannelWidget
    jam_tab.py          # JAM mode UI
  storage/
    __init__.py
    io.py               # save/load JSON
  app.py                # MainWindow
  __init__.py

tests/
  test_psg_channel.py
  test_psg_state.py
  test_synthesizer.py
  test_project_io.py

docs/
  AY-3-8914-ARCHITECTURE.md  # Hardware reference
  ARCHITECTURE.md             # This file
```

---

## What This Fixes

| Issue | Old Approach | New Approach |
|-------|--------------|--------------|
| Mixing | Noise as separate channel | Per-channel tone+noise via R7 |
| Model | "Shadow state" dict | PSGChannel dataclasses |
| UI logic | Widgets do register math | UI emits Hz/volume, model converts |
| Audio | QtMultimedia (WSL broken) | sounddevice (WSL-compatible) |
| Testability | Tight Qt coupling | Pure Python models |
| Type safety | `dict['R0']` | `channel.frequency` |

---

## Success Criteria

✅ **Real-time response:** <50ms slider-to-sound latency
✅ **WSL compatibility:** Works via PulseAudio
✅ **Correct PSG behavior:** Tone+noise mixing per channel
✅ **Clean architecture:** Matches telliGRAM patterns
✅ **Testable:** Models and synth have unit tests
✅ **Jamming workflow:** Move sliders, find sounds, save snapshots
