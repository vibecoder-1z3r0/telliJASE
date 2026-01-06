# telliJASE Project File Format

`tellijase` stores projects as deterministic UTF-8 JSON with the extension `.tellijase`. The structure balances human readability with future evolvability.

## Top-Level Layout
```json
{
  "format_version": 1,
  "meta": {
    "name": "Space Rescue Sketches",
    "created": "2024-03-15T04:38:19Z",
    "modified": "2024-03-16T01:22:03Z",
    "notes": "Initial sound pass after blocking animation."
  },
  "globals": { ... },
  "jam_sessions": [ ... ],
  "songs": [ ... ],
  "assets": { ... }
}
```
- `format_version` guards against incompatible future changes. The app must refuse to load newer formats and offer migration from older ones.
- `meta` holds user-facing info and timestamps (ISO 8601 UTC).
- `globals` contains settings shared across modes (tempo defaults, mixer calibration, envelopes, instruments).
- `jam_sessions` is an ordered list of JAM snapshots.
- `songs` is an ordered list of FRAME-mode songs.
- `assets` stores reusable presets referenced by both modes.

## Globals
```json
"globals": {
  "default_bpm": 120,
  "frame_rate": 60,
  "master_volume": 0.8,
  "envelopes": {
    "env_id": {
      "name": "Triangle Long",
      "shape": 12,
      "period": 1200,
      "notes": "Used for pads"
    }
  },
  "instruments": {
    "instr_id": {
      "name": "Bass Pulse",
      "channel_settings": {
        "tone": true,
        "noise": false,
        "envelope_id": "env_id",
        "volume": 10,
        "mixer_mask": 0
      },
      "modulators": {
        "vibrato": { "depth": 2, "speed": 5 },
        "tremolo": { "depth": 3, "speed": 3 }
      }
    }
  }
}
```
- `frame_rate` reflects the Intellivision cadence; frame counts in songs reference this value.
- Instrument presets group mixer/envelope defaults and optional automation curves.

## JAM Sessions
Each session captures the live state so that reloading reproduces the same sound immediately.
```json
{
  "id": "session_id",
  "name": "Lead Jam",
  "created": "2024-03-16T01:00:00Z",
  "updated": "2024-03-16T01:05:02Z",
  "registers": {
    "R0": 254,
    "R1": 0,
    "R2": 288,
    "R3": 0,
    "R4": 330,
    "R5": 0,
    "R6": 3,
    "R7": 0,
    "R8": 8,
    "R9": 6,
    "R10": 4,
    "R11": 200,
    "R12": 1,
    "R13": 12
  },
  "mod_curves": {
    "channel_a": { "type": "lfo", "depth": 2, "speed": 4 },
    "channel_b": { "type": "manual", "points": [[0,8],[30,12]] }
  },
  "notes": "Improv idea for intro"
}
```
- `registers` mirrors the AY-3-8914 register shadow state (14 active registers). Use integers 0–255. When saved, this ensures instantaneous recreation.
- `mod_curves` is optional and stores JAM-only automation (LFOs, manual XY pads, etc.).

## Songs (FRAME Mode)
```json
{
  "id": "song_id",
  "name": "Stage 1 Theme",
  "bpm": 110,
  "loop": true,
  "tracks": {
    "A": [ { "frame": 0, "duration": 4, "period": 254, "volume": 12, "noise": false, "envelope_id": "env_id", "instrument_id": "instr_id" }, ... ],
    "B": [ ... ],
    "C": [ ... ],
    "N": [ { "frame": 0, "duration": 2, "noise_period": 3, "volume": 15 } ]
  },
  "patterns": [
    { "id": "pat1", "name": "Verse", "length_frames": 120, "order": ["A","B","C","N"] }
  ],
  "exports": {
    "assembly": { "last_path": "stage1.asm", "options": {"optimize_redundant": true } },
    "intybasic": { "last_path": "stage1.bas", "options": {"wait_insert": true } }
  }
}
```
- Tracks keyed by channel letters (`A`, `B`, `C`, `N`). Each entry describes the state during a contiguous frame span; durations multiply by `globals.frame_rate` for seconds.
- `period`, `volume`, `noise_period`, `mixer_mask`, etc., correspond directly to PSG registers. Include only relevant attributes per channel; defaults fall back to the last event.
- `patterns` enable reusing frame sequences; pattern orders feed playback and export logic.
- `exports` caches user preferences for reproducible assembly/IntyBASIC generation.

## Assets
Shared resources for reuse across sessions and songs.
```json
"assets": {
  "samples": [],
  "comments": [
    { "id": "note1", "target": {"type": "song", "id": "song_id", "frame": 120}, "text": "Needs punchier lead" }
  ]
}
```
- Extendable bucket for future attachments (screenshots, wave captures) while keeping the main schema stable.

## Serialization Guidelines
1. Always pretty-print with 2-space indentation for git-friendly diffs.
2. Sort object keys alphabetically except when order matters (e.g., `tracks` arrays). Deterministic ordering keeps merges clean.
3. Save files directly (no swap file), matching telliGRAM’s behavior.
4. Validate before save: ensure register values are within range, referenced IDs (envelopes, instruments) exist, and durations > 0.
5. Include a checksum (`sha256`) of the serialized PSG timeline in `meta` if later integrity checks are desired.

This format gives JAM and FRAME modes first-class entries while keeping shared presets in one place, making migrations and exports straightforward.
