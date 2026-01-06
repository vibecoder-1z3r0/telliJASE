# telliJASE Agent Guide

## Mission
Build "Just A Sound Editor" for crafting AY-3-8914 (Intellivision) music and sound effects. Output should help composers preview patches, schedule events frame-by-frame, and export both CP1610 assembly and IntyBASIC sequences suitable for inclusion in ROM projects.

## Source of Truth
- Hardware reference: `AY-3-8914.md`
- Programming notes: `PROGRAMMING_THE_SOUND_CHIP.md`
- Project persistence: `PROJECT_FILE_FORMAT.md` (JSON `.tellijase` files, direct save like telliGRAM)
- UI inspiration: telliGRAM (PySide6 messaging client) — mirror layout polish, theme palette, and responsiveness expectations.
- Vibe reference art/screenshot: `For-Codex.png` (FRAME timeline inspiration).
- Licensing: MIT (`LICENSE`) + Vibe-Coder License (`VCL-0.1-Experimental.md`); always ship both.

## Attribution & Credits
- Vibe-Coder primary author: Andrew Potozniak `<vibecoder.1.z3r0@gmail.com>`. Use `Co-Authored-By: Andrew Potozniak <vibecoder.1.z3r0@gmail.com>` in git commits involving collaborative AI contributions.
- AI collaborator credit: `Co-Authored-By: Codex [GPT-5] <codex-cli@tellijase.local>` when AI contributes code/automation.
- AI Attribution statements for documentation/releases:
  - **AIA Short:** `AIA Short - AIA PAI Nc Hin R Codex [GPT-5] v1.0`
  - **AIA Full:** `AIA Full - AIA Primarily AI, New content, Human-initiated, Reviewed, Codex [GPT-5] v1.0`
  - **AIA Expanded:** `This work was primarily AI-generated. AI was used to make new content, such as text, images, analysis, and ideas. AI was prompted for its contributions, or AI assistance was enabled. AI-generated content was reviewed and approved. The following model(s) or application(s) were used: Codex [GPT-5].`
  - **Reference URL:** `https://aiattribution.github.io/statements/AIA-PAI-Nc-Hin-R-?model=%20Codex%20%5BGPT%252D5%5D-v1.0`
- Preferred model label: `Codex [GPT-5]`.

## Tech Stack Expectations
- Desktop UI: PySide6 (Qt Quick widgets acceptable if justified).
- Audio preview: Python with NumPy + simple DSP, or leverage SDL/Qt audio APIs if latency is acceptable. Must faithfully emulate PSG behavior outlined in the research docs.
- Persistence: JSON or YAML project files until a formal schema emerges. Keep conversions deterministic for version control friendliness.

## Application Modes
- **JAM Mode (tab 1):** Real-time playground where all three tone channels (plus optional noise) can be tweaked live. Provide per-channel meters, quick ADSR toggles, and combined output monitoring so it feels like one instrument feeding the AY chip.
- **FRAME Mode (tab 2):** Timeline editor inspired by telliGRAM’s animation timelines (see `For-Codex.png`). Each track represents a PSG channel (A, B, C, Noise) with frame cells showing period, volume, mixer flags, and envelope state. Support drag-to-extend, frame duration controls, and copy/paste akin to card timelines.
- Switching tabs should preserve state and keep transports (play/pause, loop, speed) in sync so auditioning transitions between improvisation and sequenced playback stays seamless.
- Both modes ultimately feed the same underlying PSG state model; avoid duplicate logic by sharing a core “register shadow state” service.
- JAM Sessions: allow multiple saved snapshots per project (e.g., “Lead Jam”, “Bass Sketch”). Persist each snapshot’s chip register state, custom modulation curves, and notes.
- Songs (FRAME): store each sequenced timeline as its own asset with pattern list, tempo, loop flags, and export metadata. Support duplicating songs for variations.
- Project saves should serialize JAM Sessions + Songs + shared resources (envelopes, instrument presets) together so reloading a project restores everything exactly as the user left it.

## Collaboration Rules
1. Keep edits incremental and well-documented; reference chip docs when adjusting DSP logic.
2. For new features, outline the UX change (sketch, screenshot, or markdown mock) before diving into code.
3. Prefer pure-Python prototypes for experimentation; once stable, integrate into PySide6 widgets/models.
4. Ensure every branch includes at least smoke-level validation: launch app, load/save project, play preview.
5. Maintain compatibility with Python 3.8+ (PySide6 6.2.4 constraint) while supporting later versions when possible.

## Code Style
- Follow PEP 8 with type hints on public functions/classes.
- Separate UI (Qt Designer `.ui` or widget classes) from PSG logic modules.
- Provide concise docstrings describing algorithmic intent, especially for frequency/period math or export serialization.
- Avoid hard-coded magic numbers; use named constants that match register names (R0_PERIOD_A_FINE, etc.).

## Testing & Tooling
- Use `pytest` for unit tests (math helpers, exporters, state machines). Default to TDD where practical: write failing tests that describe expected PSG behavior before implementing core logic.
- Add golden files for exported assembly/IntyBASIC snippets when behavior stabilizes.
- Integrate `pre-commit` hooks if the repository grows (black, isort, mypy optional but encouraged).

## UX Principles
- Frame timeline should align with the Intellivision 60 Hz cadence by default, but expose sub-frame "tick" mode for advanced scheduling.
- Provide immediate visual feedback when toggling tone/noise/envelope participation per channel.
- Keep keyboard access strong (spacebar play/stop, numeric channel selection, etc.).
- Assume composers will juggle <32 patterns; optimize navigation for quick auditioning.

## Deliverable Checklist for New Features
- [ ] Updated documentation (README snippet or relevant `.md`).
- [ ] UI screenshot or GIF when visual behavior changes.
- [ ] Tests or manual verification notes.
- [ ] Export fixtures (assembly/IntyBASIC) refreshed if the format changes.
