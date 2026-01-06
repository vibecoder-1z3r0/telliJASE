# telliJASE

## Just A Sound Editor for Intellivision
Explore Tone, Noise, and Time on Intellivision through frame-based sound design for the AY-3-8914.
(JASE pronounced like “jazz”)

## License
telliJASE is dual-licensed:

- [MIT License](LICENSE) for formal legal coverage.
- [Vibe-Coder License (VCL-0.1-Experimental)](VCL-0.1-Experimental.md) for the cultural vibes. This novelty license must accompany MIT but carries no legal force if conflicts arise.

## Development Setup
- Requires Python ≥ 3.8. We target PySide6 6.2.4 (newer builds dropped Python 3.8 wheels) and numpy 1.24.4 (latest supporting 3.8), so stick to that range unless we bump the interpreter.
- A local virtual environment lives at `./.venv/`; activate it before installing requirements or running tooling:
  ```
  source .venv/bin/activate
  pip install -r requirements-dev.txt
  python -m pytest
  ```
