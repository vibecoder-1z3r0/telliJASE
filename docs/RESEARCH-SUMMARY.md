# Research Summary: AY-3-8914 PSG for telliJASE

**Date:** 2026-01-08
**Purpose:** Deep-dive into Intellivision PSG architecture to build accurate real-time synthesizer

---

## Key Findings

### Critical Formula Corrections

**OLD (WRONG):**
```python
Frequency = CLOCK_HZ / (16 × Period)  # Missing a factor of 2!
```

**NEW (CORRECT):**
```python
Frequency = CLOCK_HZ / (32 × Period)  # Clock ÷ 16 internally, then ÷ Period
```

**Impact:** All our frequencies were **2× too high**. A 440Hz tone was actually generating ~880Hz!

### Tone + Noise Mixing Architecture

**What we thought:**
- 3 tone channels + 1 separate noise channel
- Mix them all together at the end
- Noise has its own volume

**What it actually is:**
```
Each channel has a MIXER that combines:
  - That channel's tone generator (square wave)
  - The SHARED noise generator

R7 register controls WHICH inputs feed WHICH channels:
  - Bit 0: Channel A tone enable (0=on, 1=off)
  - Bit 3: Channel A noise enable (0=on, 1=off)
  - Same pattern for B and C

Then VOLUME is applied to the MIXED signal per channel.
```

**This means you can:**
- Channel A: 100Hz tone + noise (kick drum)
- Channel B: 440Hz tone only (melody)
- Channel C: noise only (hi-hat)

All at the same time, each with independent volume!

### Register Shuffling on Intellivision

The AY-3-8914 in Intellivision has **heavily shuffled** registers compared to the standard AY-3-8910.

Example: Channel A period isn't at consecutive addresses!
- R0 (fine) → $01F0
- R1 (coarse) → $01F4 ← **Gap of 4 addresses!**

See `docs/AY-3-8914-ARCHITECTURE.md` for full mapping table.

### Intellivision-Specific Features

1. **6-bit volume control** (vs 5-bit on standard AY-3-8910)
   - Extra bits C0/C1 for envelope shifting
   - Allows quarter/half volume envelope variations

2. **Different clock**
   - NTSC: 3.579545 MHz (color subcarrier)
   - PAL: 4.000000 MHz

3. **R8/R9 used for controller input**, not general I/O

---

## What We Got Right

✅ Using numpy for synthesis
✅ Phase accumulators to avoid clicks
✅ Clock rate (3.579545 MHz for NTSC)
✅ Square wave generation approach
✅ Dataclass-based models

---

## What We Got Wrong

❌ **Frequency formula** - off by factor of 2
❌ **Noise mixing** - treated as separate channel, not per-channel
❌ **R7 mixer register** - completely ignored
❌ **Volume application** - applied to tone/noise separately instead of to mixed signal
❌ **Register map** - used simplified/guessed addresses
❌ **MAX_PERIOD** - said 1023, actually 4095 (12-bit value)

---

## Architecture Decisions

### 1. Audio Backend: sounddevice (not QtMultimedia)

**Reason:** WSL compatibility

- QtMultimedia requires GStreamer → broken in WSL
- pygame.mixer is overkill (full game engine for simple synthesis)
- **sounddevice** is lightweight, WSL-friendly, real-time callback API

### 2. Clean Model-View Separation (like telliGRAM)

**OLD approach:**
```python
"Shadow state" dict → widgets do register math → emit register updates
```

**NEW approach:**
```python
PSGChannel dataclass (freq, volume, tone_enabled, noise_enabled)
  ↓
UI emits high-level signals (frequency_changed, volume_changed)
  ↓
Model converts to registers when needed (to_registers())
  ↓
Audio engine reads model state
```

**Benefits:**
- Testable without Qt
- Type-safe (`channel.frequency` vs `dict['R0']`)
- Matches telliGRAM patterns

### 3. Streaming Audio (not one-shot playback)

**Current code:** Generate buffer → play → silence → repeat (gaps/stuttering)

**New approach:** Continuous streaming via sounddevice callback
- Audio thread calls `render_buffer()` every ~20-50ms
- Reads fresh PSG state each time
- Phase accumulators ensure smooth transitions
- **Feels real-time:** <50ms latency from slider to sound

---

## Testing Implications

The frequency error means **all existing audio is wrong**. We need to:

1. Re-test frequency conversions with corrected formula
2. Add unit tests for R7 mixer behavior:
   - Tone only
   - Noise only
   - Tone + noise mixed
   - Both disabled
3. Verify noise is shared correctly across channels
4. Test volume applied to MIXED signal, not individual generators

---

## Implementation Phases

### Phase 1: Core Models (Pure Python, Testable)
- `PSGChannel` dataclass with `to_registers()`
- `PSGState` with proper R7 mixer logic
- `Project` and `JAMSnapshot` for persistence
- Unit tests for frequency conversion, register mapping, mixing

### Phase 2: Corrected Audio Synthesis
- Fix `PSGSynthesizer` to use correct formula (÷32 not ÷16)
- Implement per-channel tone+noise mixing via R7
- Generate shared noise once, distribute to channels
- Apply volume to MIXED signal
- Unit tests for waveform generation

### Phase 3: sounddevice Integration
- `LivePSGStream` with callback-based rendering
- Graceful degradation if sounddevice missing
- Startup warning popup + logging
- Visual "audio unavailable" banner in UI

### Phase 4: Clean UI (High-Level Signals)
- `ChannelWidget` emits `frequency_changed(float)`, not register updates
- Checkboxes for tone/noise enable per channel
- Noise period slider (shared control)
- No register math in UI code

### Phase 5: Project I/O & Export
- Save/load `.tellijase` files
- JAM snapshot management (like telliGRAM's animation frames)
- Export to IntyBASIC format (register value tables)

---

## References

**Primary Source:**
- [jzintv PSG Documentation](http://spatula-city.org/~im14u2c/intv/jzintv-1.0-beta3/doc/programming/psg.txt)
  **Huge thanks to the jzintv team!** This doc saved us from shipping completely wrong audio.

**Additional:**
- [General Instrument AY-3-8910 - Wikipedia](https://en.wikipedia.org/wiki/General_Instrument_AY-3-8910)
- [PSG - Intellivision Wiki](http://wiki.intellivision.us/index.php/PSG)
- [AY-3-8914 Technical Information](https://console5.com/techwiki/images/8/88/AY-3-8914_Technical_Information.pdf)

---

## Files Created/Updated

### Documentation
- `docs/AY-3-8914-ARCHITECTURE.md` - Complete hardware reference
- `docs/ARCHITECTURE.md` - telliJASE software architecture design
- `docs/RESEARCH-SUMMARY.md` - This file

### Code Corrections
- `tellijase/psg/utils.py` - Fixed frequency formulas (÷32 not ÷16)

### Still TODO
- Refactor audio/engine.py with correct mixing
- Refactor ui/jam_controls.py to emit high-level signals
- Create models/psg_channel.py, models/psg_state.py
- Implement audio/stream.py with sounddevice
- Add proper audio availability warnings in app.py

---

## Next Steps

**Decision point:** Full refactor vs incremental fixes?

**Option A: Full Refactor (Recommended)**
- Clean slate with corrected architecture
- Testable from day one
- Matches telliGRAM patterns
- ~1-2 days of focused work

**Option B: Incremental Fixes**
- Fix formula in utils.py ✅ (done)
- Add R7 mixer to existing engine
- Keep "shadow state" approach
- Risk: technical debt accumulates

**Recommendation:** Go with Option A. The current code has fundamental architectural issues (shadow state, UI doing register math, wrong mixing). Better to rebuild on solid foundation than patch a shaky one.

The core insight - **per-channel tone+noise mixing via R7** - is central to PSG sound design. Can't fake it with the current architecture.
