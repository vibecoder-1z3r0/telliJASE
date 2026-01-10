# CLAUDE.md - Context for Future Sessions

## Project Overview

**telliJASE** (Just A Sound Editor for Intellivision) is a PySide6 desktop application for composing music for the Intellivision's AY-3-8914 PSG chip. It features:
- **JAM mode**: Real-time PSG playground for sound design
- **FRAME mode**: Tracker-style sequencer for frame-by-frame composition (1800 frames = 30 seconds at 60 FPS)

## Architecture

### Core Modules

**Models** (`tellijase/models/`)
- `psg_state.py` - PSGState and PSGChannel dataclasses (domain model, no Qt)
- Handles AY-3-8914 register conversion with correct R7 mixer logic (inverted bits)
- Thread-safe snapshots for audio callbacks
- **NOT USED**: `project.py` (old JAMSnapshot/Project, superseded by storage/)

**Audio** (`tellijase/audio/`)
- `synthesizer.py` - Pure numpy PSG synthesis with hardware-accurate mixing
  - Per-channel tone+noise AND gating (digital signal mixing)
  - Phase continuity to prevent clicks
  - LFSR noise generator (17-bit)
- `stream.py` - sounddevice (PortAudio) real-time streaming (preferred)
- `pygame_player.py` - pygame fallback for WSL/environments where sounddevice fails
- `engine.py` - AY38914Synth helper (frequency/period conversion)
- **NOT USED**: `player.py` (old QAudioSink approach, replaced by sounddevice/pygame)

**Storage** (`tellijase/storage/`)
- `project_model.py` - Project, JamSession, Song, Metadata dataclasses
- `io.py` - JSON save/load for .tellijase files
- Uses proper separation: metadata, jam sessions, songs (tracker-style)

**UI** (`tellijase/ui/`)
- `jam_controls.py` - ChannelControl widget (mixer-board layout)
  - Two-pane: frequency/mixer (left) | volume fader (right)
  - Green toggle buttons (Tone/Noise enable)
  - Red toggle button (Mute)
  - Vertical volume sliders with tick marks
  - Frequency scale labels (100, 500, 1000, 1500 Hz)
- `timeline.py` - FRAME mode timeline widgets
  - FrameCell (70x55px) - Single frame visualization with text labels
  - TrackTimeline - Row of cells for one channel/track
  - FrameTimeline - Complete 5-track view (A, B, C, Noise, Envelope)
  - FrameEditor - Panel for editing individual frame parameters
  - Copy/paste with multi-select (Ctrl+C/V/A)

**PSG Utils** (`tellijase/psg/`)
- `utils.py` - CLOCK_HZ constant, frequency/period/amplitude conversions
- **NOT USED**: `shadow_state.py` (only in tests, not in main app)

**Main** (`tellijase/main.py`)
- JAMWindow - Main PySide6 application
- Three-channel controls (A, B, C)
- Noise control (period 0-31, default=1 for audible)
- Audio backend detection (sounddevice → pygame fallback)
- Menu: File (New/Open/Save), Help (About)

## Key Technical Decisions

### Audio Backend Strategy
- **Primary**: sounddevice (PortAudio) for low-latency real-time streaming
- **Fallback**: pygame.mixer for WSL/Linux where sounddevice may fail
- **Rejected**: QAudioSink (QtMultimedia) - dependency issues, replaced by above
- Detection order: Try sounddevice first, fall back to pygame if unavailable

### AY-3-8914 PSG Emulation
- **R7 Mixer Logic**: Inverted bits (0=enable, 1=disable)
  - Bits 0-2: Tone enable for channels A, B, C
  - Bits 3-5: Noise enable for channels A, B, C
- **Tone+Noise Mixing**: Digital AND gate (both signals must be HIGH)
  - NOT simple addition - hardware-accurate digital logic
- **Noise Period**: 0 = OFF (silent), 1+ = audible (default changed to 1)
- **Frequency Range**: 27-2000 Hz (hardware min to musical range)
- **Volume**: 0-15 per channel, applied AFTER mixing

### UI/UX Design

**JAM Mode:**
- **Mixer-board aesthetic**: Vertical volume faders with tick marks
- **Color coding**: Green=enabled, Red=muted, Gray=disabled
- **Default power chord**: A2 (110 Hz), A3 (220 Hz), E4 (330 Hz)
- **Precision controls**: Slider + text input, page step=1 for fine adjustments
- **Mute behavior**: Stores volume, disables slider, restores on unmute

**FRAME Mode:**
- **Timeline**: 1800 frames (30 seconds at 60 FPS NTSC timing)
- **Frame visualization**: Text-based display in each cell
  - Line 1: Frequency (e.g., "440Hz")
  - Line 2: Volume (e.g., "V:10")
  - Line 3: Tone/Noise indicators ("T" green, "N" orange)
- **Visual feedback**:
  - Yellow border (3px): Current playback position
  - Cyan border (2px): Selected for copy/paste
  - Blue border (1px): Filled with data
  - Gray border (1px): Empty frame
- **Copy/paste workflow**:
  - Ctrl+Click: Toggle frame selection
  - Ctrl+C: Copy selected frames
  - Ctrl+V: Paste frames
  - Ctrl+A: Select all filled frames
  - Status bar shows operation feedback
- **Transport controls**: Play, Pause, Stop, Loop toggle
- **Frame editor**: Side panel for editing individual frames

## Development Workflow

### Python Version Support
- Python 3.8-3.14 (tested in CI)
- Version-specific numpy constraints:
  - 3.8: numpy 1.21-1.25
  - 3.9: numpy 1.21-1.27
  - 3.10+: numpy 1.21+
- PySide6 6.2.0-6.9.0 (all Python versions)

### CI/CD (GitHub Actions)
Three jobs run on Python 3.8-3.13:
1. **Test**: pytest with coverage (offscreen QT_QPA_PLATFORM)
2. **Lint**: flake8 (E9/F63/F7/F82 + complexity/line-length), black, mypy
3. **PySide6 compatibility**: Verify imports across all Python versions

### Code Quality Standards
- **flake8**: max-line-length=100, max-complexity=10
- **black**: Target py38-py313
- Install package in editable mode (`pip install -e .`) before tests/lints

### Testing
- All tests in `tests/` using pytest (16 tests currently)
- Focus on domain models, audio engine, storage I/O
- Mock Qt where needed (QT_QPA_PLATFORM=offscreen in CI)
- **Storage tests**: JAM sessions, Songs with TrackEvents, multi-song projects
- **Register validation**: Tests use PSGState.to_registers() to catch schema bugs

## Common Issues & Solutions

### WSL/Linux Audio
- **Problem**: sounddevice may not work (missing PortAudio)
- **Solution**: Install `libportaudio2 portaudio19-dev`, or use pygame fallback
- **Detection**: App auto-detects and uses pygame if sounddevice unavailable

### Noise Period Behavior
- **Problem**: Default 0 makes noise inaudible even when mixed
- **Solution**: Changed default to 1 (R6=1) so noise is ready to use

### Mute Button UX
- **Problem**: Users could mute by setting volume to 0, losing previous value
- **Solution**: Dedicated MUTE button stores volume, disables slider, restores on unmute

### flake8 Complexity
- **Problem**: PSGSynthesizer.render_buffer was too complex (C901)
- **Solution**: Extracted `_process_channel` and `_update_phase` methods

### Register Validation Bug (R14/R15)
- **Problem**: "Unknown register key R14" when saving JAM sessions with envelope
- **Root cause**: REGISTER_KEYS in project_model.py only had R0-R13, missing R14/R15 for envelope
- **Solution**: Added R14 (envelope period high) and R15 (envelope shape) to REGISTER_KEYS
- **Prevention**: Tests now use PSGState.to_registers() to simulate actual UI flow

## File Organization

```
tellijase/
├── __init__.py           # Package version
├── __main__.py          # Entry point (python -m tellijase)
├── main.py              # JAMWindow - main application
├── audio/
│   ├── __init__.py      # Exports: AY38914Synth, PSGSynthesizer, LivePSGStream
│   ├── engine.py        # AY38914Synth (used by tests)
│   ├── pygame_player.py # Pygame fallback
│   ├── stream.py        # sounddevice streaming
│   └── synthesizer.py   # Pure numpy PSG synthesis
├── models/
│   ├── __init__.py      # Exports: PSGChannel, PSGState
│   ├── psg_channel.py   # Single channel model
│   └── psg_state.py     # Full PSG state (3 channels + noise + envelope)
├── psg/
│   ├── __init__.py      # (shadow_state.py only used in tests)
│   └── utils.py         # CLOCK_HZ, conversions
├── storage/
│   ├── __init__.py      # Exports: Project, JamSession, Song, Metadata, load/save/new
│   ├── io.py            # JSON persistence
│   └── project_model.py # Data models for .tellijase files
└── ui/
    ├── jam_controls.py  # ChannelControl widget
    └── timeline.py      # FrameCell, TrackTimeline, FrameTimeline, FrameEditor

tests/
├── test_audio_engine.py
├── test_project_io.py
├── test_project_model.py
├── test_psg_state.py
└── test_shadow_state.py # (shadow_state only used here)
```

## Future Features

- **Envelope controls**: env_period, env_shape in main.py (lines commented, not deleted)
- **Track-level Mute/Solo**: Channel mute/solo buttons for FRAME mode (not per-frame)
- **Export**: .BIN files for Intellivision, WAV export
- **Inline frame editing**: Edit frames directly in timeline (currently via side panel)
- **Frame duration**: Currently all frames are 1-frame duration, could add variable lengths

## Lessons Learned

### Always Test Defaults
- Changing noise_period default required updating test_psg_state.py
- Tests should validate sensible defaults, not just "zero everything"

### Audio Threading
- Use thread-safe snapshots for PSG state in audio callbacks
- sounddevice runs audio callback in separate thread
- pygame uses manual threading with queue-based buffer updates

### Qt Best Practices
- Block signals when updating UI from model (avoid feedback loops)
- Use QGroupBox for logical control grouping
- Vertical sliders need explicit minimum height for good UX
- Toggle buttons (setCheckable) are cleaner than checkboxes for binary states

### Dependency Management
- Always use version-specific constraints for numpy (varies by Python version)
- Install package before running tests (`pip install -e .`)
- Test across Python versions (3.8-3.13) to catch compatibility issues

### FRAME Mode Implementation
- **Timeline scale**: 1800 frames (30 sec) provides good balance for music composition
- **Text visualization**: More informative than abstract bars for small cells
- **Copy/paste architecture**: Store clipboard at widget level, emit signal for main window to apply
- **Selection state**: Track at cell level, allows for flexible multi-select patterns
- **Audio initialization**: FRAME mode should use identical backend logic to JAM mode (don't reinvent)

### Storage Schema Validation
- When adding new register fields (R14/R15), update REGISTER_KEYS in project_model.py
- Write tests that use actual data flow (PSGState.to_registers()) not just schema checks
- Register validation bugs manifest when saving, not loading - test both directions

### Visual Feedback
- Border hierarchy for cells: Playback (yellow, 3px) > Selection (cyan, 2px) > Filled (blue, 1px) > Empty (gray, 1px)
- Status bar messages should confirm user actions (copy/paste counts)
- Use QPainter custom rendering for frame cells instead of complex widget composition

## Quick Start for New Sessions

1. **Understand the task**: JAM mode improvements, FRAME mode enhancements, export features, etc.
2. **Check imports**:
   - Main app uses PSGState, LivePSGStream/PygamePSGPlayer, ChannelControl
   - FRAME mode uses FrameTimeline, FrameEditor from ui.timeline
3. **Run tests first**: `pytest --tb=short` to ensure nothing is broken (16 tests)
4. **Follow code quality**: Run `flake8` and `black` before committing
5. **Update tests**: If changing defaults or behavior, update test expectations
6. **Document in CLAUDE.md**: Add new architectural decisions or lessons learned

## Current State (as of 2025-01)

**Implemented:**
- ✅ JAM mode with real-time PSG playground
- ✅ FRAME mode with 1800-frame timeline (30 sec at 60 FPS)
- ✅ Copy/paste with multi-select (Ctrl+C/V/A)
- ✅ Text-based frame visualization
- ✅ Frame playback with transport controls
- ✅ Project save/load for both JAM sessions and FRAME sequences
- ✅ Audio backend fallback (sounddevice → pygame)

**Pending:**
- ⏳ Track-level Mute/Solo for FRAME mode
- ⏳ Inline frame editing (double-click)
- ⏳ Envelope controls (UI commented out, ready to implement)
- ⏳ Export to .BIN and WAV

## Contact & Resources

- Repository: https://github.com/vibecoder-1z3r0/telliJASE
- Dual license: MIT + VCL-0.1-Experimental (novelty license)
- AY-3-8914 datasheet: Reference for R7 mixer logic and register behavior
