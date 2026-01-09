# telliJASE

## Just A Sound Editor for Intellivision
Explore Tone, Noise, and Time on Intellivision through frame-based sound design for the AY-3-8914.
(JASE pronounced like “jazz”)

## License
telliJASE is dual-licensed:

- [MIT License](LICENSE) for formal legal coverage.
- [Vibe-Coder License (VCL-0.1-Experimental)](VCL-0.1-Experimental.md) for the cultural vibes. This novelty license must accompany MIT but carries no legal force if conflicts arise.

## Development Setup

### Python & Dependencies
- **Python 3.8 through 3.14** supported
- **PySide6 6.2.0-6.9.0** - Supports all Python versions
- **NumPy**: Version-specific ranges for compatibility:
  - Python 3.8: numpy 1.21-1.25
  - Python 3.9: numpy 1.21-1.27
  - Python 3.10+: numpy 1.21+

### Installation
A local virtual environment lives at `./.venv/`; activate it before installing requirements or running tooling:
```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest
```

### Audio Backends
telliJASE supports two audio backends for real-time PSG playback:
- **sounddevice** (PortAudio) - Preferred for low-latency audio
- **pygame** - Fallback option

On WSL/Linux, you may need system libraries:
```bash
sudo apt-get install libportaudio2 portaudio19-dev
```

### CI/Testing
Multi-version CI testing runs on Python 3.8, 3.9, 3.10, 3.11, 3.12, and 3.13 using GitHub Actions. See `.github/workflows/ci.yml` for details.
