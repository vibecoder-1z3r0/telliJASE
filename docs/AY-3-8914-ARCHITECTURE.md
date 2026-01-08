# AY-3-8914 PSG Architecture Notes

## Overview

The AY-3-8914 is the Intellivision's Programmable Sound Generator (PSG), part of the General Instrument AY-3-891x family. It's functionally similar to the AY-3-8910 but with **register shuffling** and **Intellivision-specific modifications**.

**Key Specs:**
- 3 tone channels (A, B, C)
- 1 shared noise generator
- 1 envelope generator
- Clock: 3.579545 MHz (NTSC color subcarrier)
- Output: Mixed analog audio

---

## Critical Architecture Details

### Mixing Topology

**The AY-3-8914 does NOT have separate tone and noise output channels.**

Each of the 3 channels has a **mixer** that combines:
- Tone generator output (channel-specific square wave)
- Noise generator output (shared across all channels)

```
Channel A:                  Channel B:                  Channel C:
┌─────────┐                ┌─────────┐                ┌─────────┐
│ Tone A  │───┐            │ Tone B  │───┐            │ Tone C  │───┐
└─────────┘   │            └─────────┘   │            └─────────┘   │
              ├─[Mixer]──▶ Vol A ──┐     ├─[Mixer]──▶ Vol B ──┐    ├─[Mixer]──▶ Vol C ──┐
┌─────────┐   │                    │     │                    │    │                    │
│ Noise   │───┘                    ├─────┴────────────────────┴────┘                    │
│(shared) │────────────────────────┘                                                    │
└─────────┘                                                                             │
                                                                                        ▼
                                                                                    [Final Mix]
                                                                                        │
                                                                                        ▼
                                                                                     Output
```

**R7 Mixer Control** determines which inputs feed each channel:
- Bit 0: Channel A tone enable (0=enabled, 1=disabled)
- Bit 1: Channel B tone enable
- Bit 2: Channel C tone enable
- Bit 3: Channel A noise enable (0=enabled, 1=disabled)
- Bit 4: Channel B noise enable
- Bit 5: Channel C noise enable
- Bits 6-7: I/O port direction (not used for sound)

**Inverted logic:** 0 = enabled, 1 = disabled

### Possible Channel Configurations

| R7 Bits (Tone/Noise) | Output |
|---------------------|--------|
| 0/0 (both enabled)  | Tone AND noise mixed together |
| 0/1 (tone only)     | Pure tone (square wave) |
| 1/0 (noise only)    | Pure noise |
| 1/1 (both disabled) | Silence (volume still applies) |

---

## Register Map (Intellivision Addresses)

**IMPORTANT:** The AY-3-8914 has **heavily shuffled registers** compared to the AY-3-8910. The logical register numbers (R0-R15) map to different physical addresses on the Intellivision.

**Source:** jzintv psg.txt documentation

| Logical Register | Inty Address | Function | Bits |
|-----------------|--------------|----------|------|
| R0 | $01F0 | Channel A Tone Period (Fine) | 8 bits |
| R1 | $01F4 | Channel A Tone Period (Coarse) | 4 bits |
| R2 | $01F1 | Channel B Tone Period (Fine) | 8 bits |
| R3 | $01F5 | Channel B Tone Period (Coarse) | 4 bits |
| R4 | $01F2 | Channel C Tone Period (Fine) | 8 bits |
| R5 | $01F6 | Channel C Tone Period (Coarse) | 4 bits |
| R6 | $01F9 | Noise Period | 5 bits |
| R7 | $01F8 | Mixer Control (Enable) | 8 bits |
| R8* | $01FE | I/O Port A (right controller) | 8 bits |
| R9* | $01FF | I/O Port B (left controller) | 8 bits |
| R10 | $01FB | Channel A Volume | 6 bits** |
| R11 | $01FC | Channel B Volume | 6 bits** |
| R12 | $01FD | Channel C Volume | 6 bits** |
| R13 | $01F3 | Envelope Period (Fine) | 8 bits |
| R14 | $01F7 | Envelope Period (Coarse) | 8 bits |
| R15 | $01FA | Envelope Shape | 4 bits |

*R8/R9 are used for controller input on Intellivision, not general I/O
**Intellivision-specific: 6-bit volume control (standard AY-3-8910 is 5-bit)

---

## Tone Generation

**Formula (CORRECTED):**
```
Frequency (Hz) = CLOCK_HZ / (32 × Period)
Period = (Coarse << 8) | Fine

where:
  CLOCK_HZ = 3,579,545 Hz (NTSC Intellivision)
            4,000,000 Hz (PAL Intellivision)
  Period = 12-bit value (0-4095), effective range 1-4095
```

**CRITICAL:** The PSG divides the clock by **32**, not 16:
- First divides by 16 internally
- Then divides by the Period value
- Total division: 16 × Period

**Range (NTSC):**
- Min frequency: 3,579,545 / (32 × 4095) ≈ **27.3 Hz**
- Max frequency: 3,579,545 / (32 × 1) ≈ **111.9 kHz** (ultrasonic)
- Musical range: ~27 Hz (A0) to ~7 kHz

**Waveform:** Square wave (50% duty cycle)

---

## Noise Generation

**Single shared noise generator** used by all channels via mixer.

**Period Control (R6):** 5 bits (0-31)
```
Noise Frequency = CLOCK_HZ / (32 × Period)
```

**Same divider as tone:** Clock ÷ 16 internally, then ÷ Period

- Period 0: Noise disabled
- Low period (1-5): High-pitched hiss
- High period (20-31): Low rumble

**Waveform:** Pseudo-random bit sequence (17-bit LFSR)

---

## Volume Control (R8, R9, R10)

**Standard AY-3-8910:** 5 bits
- Bits 0-3: Volume level (0-15, linear or logarithmic depending on chip variant)
- Bit 4: Envelope mode (1=use envelope, 0=use fixed volume)

**Intellivision-specific (6-bit):**
- Bits 0-3: Volume level (0-15)
- Bit 4: Envelope mode (M bit)
- Bit 5: Combined with M to form C0/C1 for envelope shifting

**Envelope shifting** (Intellivision only):
- C0C1 = 00: Envelope output >> 0 (full volume)
- C0C1 = 01: Envelope output >> 1 (half volume)
- C0C1 = 10: Envelope output >> 2 (quarter volume)
- C0C1 = 11: Envelope output >> 2 (quarter volume)

---

## Envelope Generator

The envelope generator provides **dynamic volume control** over time, useful for attack/decay effects.

**Registers:**
- R13/R14: Envelope period (16-bit)
- R15: Envelope shape (4 bits)

**Envelope Period (CORRECTED):**
```
Envelope Frequency = CLOCK_HZ / (512 × Period)

where Period is the full 16-bit value from R13 (fine) and R14 (coarse)
```

**Division breakdown:**
- Clock ÷ 256 internally
- Then ÷ Period value
- Then ÷ 16 (envelope is 16 steps per cycle)
- Total: Clock ÷ (256 × Period) per step, or Clock ÷ (512 × Period) per full cycle

**Envelope Shapes (R15 bits 0-3):**
- Bit 0: HOLD - freeze envelope at end
- Bit 1: ALTERNATE - reverse direction on each repeat
- Bit 2: ATTACK - start high (inverted sawtooth)
- Bit 3: CONTINUE - repeat envelope

Common patterns:
- `0x00-0x03`: Single decay
- `0x04-0x07`: Single attack
- `0x08`: Continuous decay (sawtooth down)
- `0x0A`: Triangle wave
- `0x0C`: Continuous attack (sawtooth up)
- `0x0E`: Inverted triangle

---

## Intellivision-Specific Differences

1. **Register address shuffling** - R6 and R7 swapped positions
2. **6-bit volume control** - Extra C0/C1 bits for envelope shifting
3. **Chip variants:**
   - AY-3-8914 (original Intellivision)
   - AY-3-8914A / AY-3-8916 (Intellivision II) - slight audio differences
   - Some games sound different between variants

4. **No I/O ports used** - Bits 6-7 of R7 unused in Intellivision

---

## Implications for telliJASE

### What We Got Wrong

1. **Frequency formula:** Used `CLOCK / (16 × Period)`
   - **Correct:** `CLOCK / (32 × Period)` - divides by 16 internally, then by Period

2. **Noise mixing:** Current code adds noise as a separate channel
   - **Correct:** Noise mixes PER-CHANNEL via R7 control

3. **Volume application:** Applied to tone and noise separately
   - **Correct:** Volume applies to the MIXED tone+noise signal

4. **R7 ignored:** Mixer register not used at all
   - **Critical:** R7 determines which channels output tone, noise, or both

5. **Register map:** Used simplified/assumed mapping
   - **Correct:** Intellivision has heavily shuffled registers (see table above)

### What We Got Right

1. ✅ Clock rate: 3.579545 MHz (NTSC)
2. ✅ Square wave generation approach
3. ✅ Numpy-based synthesis approach
4. ✅ Phase accumulator concept

---

## References

**Primary Source:**
- [jzintv PSG Documentation](http://spatula-city.org/~im14u2c/intv/jzintv-1.0-beta3/doc/programming/psg.txt) - Comprehensive AY-3-8914 documentation for Intellivision, including register map, formulas, and envelope patterns. **Thank you to the jzintv team for this invaluable reference!**

**Additional Sources:**
- [General Instrument AY-3-8910 - Wikipedia](https://en.wikipedia.org/wiki/General_Instrument_AY-3-8910)
- [PSG - Intellivision Wiki](http://wiki.intellivision.us/index.php/PSG)
- [AY-3-8914 Technical Information (Console5)](https://console5.com/techwiki/images/8/88/AY-3-8914_Technical_Information.pdf)
- Web search results on AY-3-8914 datasheet and Intellivision implementation

---

## Next Steps for Implementation

1. Create proper `PSGChannel` model with tone/noise enable flags
2. Implement R7 mixer control in synthesis engine
3. Mix tone+noise BEFORE applying volume
4. Support envelope generator (future phase)
5. Test with real Intellivision sound effects (drums, explosions)
