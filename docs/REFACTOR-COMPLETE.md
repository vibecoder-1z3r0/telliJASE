# Refactor Complete: telliJASE Architecture Overhaul

**Date:** 2026-01-08
**Commits:** caa34a6 (research) → 0a3ed8c (refactor)
**Status:** ✅ Complete, all tests passing (13/13)

---

## What Changed

### Before (Problems)

```
❌ "Shadow state" dict - stringly-typed, not testable
❌ Noise as separate channel - wrong mixing topology
❌ No R7 mixer - can't do tone+noise on same channel
❌ QtMultimedia - broken in WSL
❌ One-shot audio - gaps between playback
❌ UI doing register math - tight coupling
❌ Frequency formula off by 2× - all audio wrong pitch
```

### After (Solutions)

```
✅ PSGChannel/PSGState models - type-safe, testable
✅ Per-channel tone+noise mixing via R7 (hardware-accurate!)
✅ sounddevice streaming - WSL-compatible, real-time
✅ Continuous audio - smooth parameter changes
✅ High-level UI signals - clean model-view separation
✅ Correct frequency formula - CLOCK / (32 × Period)
```

---

## New File Structure

```
tellijase/
  models/          ← NEW: Domain models (pure Python)
    psg_channel.py - PSGChannel dataclass
    psg_state.py   - PSGState with R7 mixer logic
    project.py     - JAMSnapshot, Project

  audio/
    synthesizer.py - NEW: Correct per-channel mixing
    stream.py      - NEW: sounddevice real-time streaming
    engine.py      - OLD: AY38914Synth (kept for compatibility)
    player.py      - OLD: JamAudioPlayer (QtMultimedia)

  ui/
    jam_controls.py - REFACTORED: High-level signals

  app.py - REFACTORED: Clean model-view wiring

docs/
  AY-3-8914-ARCHITECTURE.md - Hardware reference
  ARCHITECTURE.md            - Software design
  RESEARCH-SUMMARY.md        - What we learned
  REFACTOR-COMPLETE.md       - This file

tests/
  test_psg_state.py - NEW: Model tests (5 tests)
  (8 existing tests still pass)
```

---

## Architecture Highlights

### 1. Clean Model-View Separation (telliGRAM Style)

```python
# Models (pure Python, no Qt)
from tellijase.models import PSGChannel, PSGState

channel = PSGChannel(frequency=440.0, volume=12)
channel.tone_enabled = True
channel.noise_enabled = False  # R7 mixer control!

# UI emits high-level signals
class ChannelControl(QGroupBox):
    frequency_changed = Signal(float)  # Not register updates!
    volume_changed = Signal(int)
    tone_enabled_changed = Signal(bool)
    noise_enabled_changed = Signal(bool)

# MainWindow wires signals to model
control.frequency_changed.connect(
    lambda freq: setattr(state.channel_a, 'frequency', freq)
)
```

### 2. Correct Per-Channel Tone+Noise Mixing

**The Key Fix!**

```python
# OLD (WRONG) - noise as separate channel
mix = tone_a + tone_b + tone_c + noise

# NEW (CORRECT) - per-channel mixing via R7
for channel in [A, B, C]:
    channel_signal = 0

    if tone_enabled:  # R7 bit 0/1/2
        channel_signal += tone_generator

    if noise_enabled:  # R7 bit 3/4/5
        channel_signal += noise_generator  # Shared!

    channel_signal *= volume  # AFTER mixing!
    mix += channel_signal
```

**Why this matters:**
- Channel A: 100Hz tone + noise → kick drum
- Channel B: 440Hz tone only → melody
- Channel C: noise only → hi-hat

**Can't do this with the old architecture!**

### 3. Real-Time Streaming (sounddevice)

```python
class LivePSGStream:
    def _callback(self, outdata, frames, time, status):
        # Called by audio thread every ~20-50ms
        state = self.psg_state.snapshot()  # Thread-safe
        samples = self.synth.render_buffer(frames, state)
        outdata[:] = samples  # Fill buffer

    def start(self):
        self.stream = sd.OutputStream(callback=self._callback)
        self.stream.start()  # Continuous playback!
```

**Benefits:**
- Slider move → hear change in <50ms (feels instant)
- No gaps or stuttering
- WSL-compatible (PortAudio → PulseAudio)

### 4. Thread-Safe State Access

**No locks needed!**

```
UI Thread:
  slider.valueChanged → state.channel_a.frequency = 880.0
  (simple field assignment, atomic in Python)

Audio Thread (every 20ms):
  snapshot = state.snapshot()  # dataclass copy
  render_buffer(snapshot)

Worst case: One 20ms buffer has mixed old/new params (imperceptible)
```

---

## Testing

All tests passing:

```bash
$ python -m pytest tests/ -v
collected 13 items

test_audio_engine.py ..          ✅ Old engine still works
test_project_io.py .             ✅ Save/load projects
test_project_model.py ...        ✅ Project model
test_psg_state.py .....          ✅ NEW: PSGState with R7 mixer
test_shadow_state.py ..          ✅ Old shadow state

13 passed in 0.49s
```

---

## Usage Example

### JAM Mode Workflow

1. **Launch app:**
   ```bash
   python -m tellijase
   ```

2. **If audio unavailable:**
   - Popup warns: "sounddevice not found, install with pip install sounddevice"
   - Status banner shows: "⚠️ Audio unavailable"
   - Play/Stop buttons disabled

3. **With audio:**
   - Click "Play Preview"
   - Move frequency slider → hear pitch change instantly
   - Check "Tone" + "Noise" → hear tone+noise mixed
   - Uncheck "Tone" → pure noise
   - Click "Snapshot" → save current state
   - Click "Stop" → silence

### Per-Channel Mixing Example

```python
# Create kick drum sound on channel A
state.channel_a.frequency = 55.0      # Low tone
state.channel_a.volume = 15           # Full volume
state.channel_a.tone_enabled = True   # R7 bit 0 = 0
state.channel_a.noise_enabled = True  # R7 bit 3 = 0

# Play melody on channel B
state.channel_b.frequency = 440.0
state.channel_b.volume = 12
state.channel_b.tone_enabled = True   # Tone only
state.channel_b.noise_enabled = False

# Hi-hat on channel C
state.channel_c.frequency = 1000.0    # Doesn't matter
state.channel_c.volume = 8
state.channel_c.tone_enabled = False  # Noise only
state.channel_c.noise_enabled = True

state.noise_period = 5  # High-pitched noise

# All three channels play simultaneously with proper mixing!
```

---

## Migration Notes

### For Future Development

**Old code still works** (for now):
- `ShadowState` still exists in `psg/shadow_state.py`
- `AY38914Synth` still exists in `audio/engine.py`
- `JamAudioPlayer` still exists in `audio/player.py`

**New code should use:**
```python
from tellijase.models import PSGChannel, PSGState
from tellijase.audio import PSGSynthesizer, LivePSGStream
```

**If you need to migrate old snapshots:**
```python
# Old format (registers dict)
old_regs = {"R0": 100, "R1": 2, "R10": 12, ...}

# Convert to new model
state = PSGState.from_registers(old_regs)

# Use new model
state.channel_a.frequency = 880.0  # Type-safe!
```

---

## Known Limitations

1. **sounddevice not available in headless environments**
   - Expected: App shows warning, disables audio
   - Can still edit/save PSG settings
   - Audio works in WSL with PulseAudio

2. **Envelope generator not implemented yet**
   - Models support it (envelope_period, envelope_shape)
   - Synthesizer doesn't use it yet
   - Future phase: Add envelope modulation

3. **Noise LFSR simplified**
   - Current: Simplified 17-bit LFSR
   - Future: Hardware-accurate LFSR for bit-perfect noise

4. **Old storage layer compatibility**
   - Old `storage/project_model.py` still in use
   - New `models/project.py` exists but not wired to I/O yet
   - Future: Migrate storage to use new models

---

## Next Steps

### Immediate (Working)
- ✅ Models with R7 mixer
- ✅ Correct frequency formula
- ✅ Per-channel tone+noise mixing
- ✅ sounddevice streaming
- ✅ All tests passing

### Phase 2 (Future)
- [ ] Envelope generator implementation
- [ ] Accurate 17-bit LFSR noise
- [ ] Noise period slider in UI
- [ ] FRAME mode sequencer (timeline editor)
- [ ] Export to IntyBASIC format

### Phase 3 (Polish)
- [ ] Migrate storage to new models
- [ ] Remove old shadow_state/engine/player code
- [ ] Real-time waveform visualizer
- [ ] Preset library (bass drum, snare, etc.)

---

## Credits

**Primary Reference:**
- [jzintv PSG Documentation](http://spatula-city.org/~im14u2c/intv/jzintv-1.0-beta3/doc/programming/psg.txt)

Without this doc, we'd have shipped wrong frequency formula, wrong mixing, and wrong register map. Thank you jzintv team!

**Additional Sources:**
- General Instrument AY-3-8910 Wikipedia
- Intellivision Wiki PSG page
- Console5 AY-3-8914 datasheet

---

## Summary

**We did the needful! 🎵**

The refactor implements:
1. ✅ **Correct PSG behavior** - per-channel tone+noise mixing
2. ✅ **Clean architecture** - testable models, type-safe
3. ✅ **Real-time audio** - continuous streaming, WSL-friendly
4. ✅ **telliGRAM patterns** - matches your existing workflow

**All tests pass. Ready to jam!**

Move a slider, hear the PSG respond instantly. Check "Tone + Noise" on a channel and create that authentic Intellivision kick drum sound. This is what we set out to build.
