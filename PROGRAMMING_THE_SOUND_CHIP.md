# Programming the AY-3-8914 on Intellivision

This note distills practical steps for driving the PSG from both raw CP1610 assembly and IntyBASIC so the editor can export runnable snippets.

## Memory-Mapped Interface
- Intellivision exposes two PSG ports:
  - `PSG_ADDR` at `$01F0`: write the target register number (0–15).
  - `PSG_DATA` at `$01F1`: write the value for the previously latched register.
- Registers are write-only. Readbacks always yield the open bus, so mirror desired state in RAM if the tool expects to tweak existing values.
- A write cycle requires ~3 PSG clocks after `PSG_DATA` commits; insert at least one `NOP` if you must update the same register consecutively in a time-critical routine.

## Assembly Patterns
### Minimal Register Write Macro
```asm
PSG_ADDR    EQU     $01F0
PSG_DATA    EQU     $01F1

; R0 = register index, R1 = value
WRITE_PSG   MACRO
            MVO     R0, @PSG_ADDR
            MVO     R1, @PSG_DATA
            ENDM
```

### Example: Set Channel A to a 440 Hz tone at half volume
```asm
; Assume 1.7897725 MHz clock; target N = clock / (16 * freq) ≈ 254
        MVII    #0, R0          ; R0 = register 0 (fine period)
        MVII    #$FE, R1        ; 254 decimal
        WRITE_PSG
        MVII    #1, R0          ; coarse bits
        MVII    #$00, R1        ; upper 2 bits cleared
        WRITE_PSG
        MVII    #7, R0          ; mixer: enable all tone, disable noise
        MVII    #%00111000, R1  ; tone A/B/C on, noise off
        WRITE_PSG
        MVII    #8, R0          ; amplitude A
        MVII    #8, R1          ; 50% volume
        WRITE_PSG
```
- When enabling noise on a voice, set the corresponding tone disable bit only if you need pure noise; otherwise the chip mixes tone+noise.
- Envelope-triggered channels require writing R13 **after** R8/R9/R10 with bit4 set.

### Timed Effects
- Vibrato/tremolo: update the coarse/fine period or amplitude every video frame (60 Hz) inside the main loop.
- Arpeggios: store chord period values in a table and rotate through them rapidly (every 2–4 frames) to simulate more voices.

## IntyBASIC Interaction
IntyBASIC provides high-level statements that translate to PSG writes during compilation:

- `SOUND channel, period, volume [,tone_mask [,noise_mask]]` writes tone period registers and amplitudes. `channel` = 0/1/2 maps to PSG channels A/B/C. The optional masks describe whether tone or noise bits in R7 should be cleared (enable) or set (disable).
- `ENVELOPE index, period, shape` preloads tables so later `SOUND` calls can enable envelope mode by supplying `volume = 16 + channel_volume` (compiler sets bit4 automatically).
- `NOISE period` modifies R6 globally; use sparingly since it impacts all channels that allow noise.
- `PLAY`/`MUSIC` statements sequence multiple `SOUND` invocations and wait for vertical blank automatically, ideal for exporting patterns.

### Example IntyBASIC Snippet
```basic
' Simple pulse lead with vibrato
NOISE 0                     ' disable noise contribution
ENVELOPE 0, 1200, 12        ' long triangle envelope

FOR i=0 TO 95
  pitch = 350 + (SIN(i*8) * 3)
  SOUND 0, pitch, 16 + 12   ' channel 0 uses envelope 0 with base level 12
  SOUND 1, pitch+30, 9
  WAIT                      ' sync to 60 Hz frame
NEXT i
```
- IntyBASIC uses CPU cycles between `WAIT` statements to update the PSG; plan exported macros so they align with this cadence.
- Because IntyBASIC values are abstract (pitch units are raw period counts), provide conversion helpers inside the editor (e.g., map `note -> period`).

## Recommended Export Strategy for the Editor
1. Maintain an internal shadow copy of all 14 active registers so emitted assembly can skip redundant writes.
2. Offer dual export modes:
   - **Assembly Macro Script:** sequence of register writes/time delays for inclusion in a CP1610 routine.
   - **IntyBASIC Blocks:** `SOUND`/`WAIT` statements grouped per frame or pattern.
3. Quantize automation lanes to the 60 Hz video clock by default, but allow sub-frame events for advanced users (document CPU burden).
4. Always emit mixer (R7) and noise (R6) changes explicitly when a channel toggles tone/noise participation to avoid hidden state carry-over between patterns.
