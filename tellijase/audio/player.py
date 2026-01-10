"""Qt audio playback utilities for JAM mode."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QByteArray, QBuffer, QObject, QIODevice

try:  # QtMultimedia may be missing gstreamer libs on some setups
    from PySide6.QtMultimedia import QAudioFormat, QAudioSink
except ImportError:  # pragma: no cover - depends on system libs
    QAudioFormat = None  # type: ignore[assignment]
    QAudioSink = None  # type: ignore[assignment]

from .engine import AY38914Synth


@dataclass
class JamAudioSettings:
    sample_rate: int = 44_100
    duration_seconds: float = 1.5


class JamAudioPlayer(QObject):
    """Wraps QAudioSink to play rendered AY samples."""

    def __init__(
        self,
        parent: QObject | None = None,
        settings: JamAudioSettings | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings or JamAudioSettings()
        self.synth = AY38914Synth(sample_rate=self.settings.sample_rate)
        self.available = QAudioFormat is not None and QAudioSink is not None

        if self.available:
            fmt = QAudioFormat()
            fmt.setSampleRate(self.settings.sample_rate)
            fmt.setChannelCount(1)
            fmt.setSampleFormat(QAudioFormat.Int16)
            self.audio_sink = QAudioSink(fmt, self)  # type: ignore[arg-type]
            self.buffer = QBuffer()
        else:
            self.audio_sink = None
            self.buffer = None
        self.data = QByteArray()

    def play(self, registers: dict[str, int]) -> bool:
        if not self.available or self.audio_sink is None or self.buffer is None:
            return False
        samples = self.synth.render(registers, self.settings.duration_seconds)
        pcm = self._to_int16(samples)
        self.data = QByteArray(pcm.tobytes())
        if self.buffer.isOpen():
            self.buffer.close()
        self.buffer.setData(self.data)
        self.buffer.open(QIODevice.ReadOnly)
        self.audio_sink.stop()
        self.audio_sink.start(self.buffer)
        return True

    def stop(self) -> None:
        if not self.available or self.audio_sink is None or self.buffer is None:
            return
        self.audio_sink.stop()
        if self.buffer.isOpen():
            self.buffer.close()

    @staticmethod
    def _to_int16(samples: np.ndarray) -> np.ndarray:
        clipped = np.clip(samples, -1.0, 1.0)
        return (clipped * 32767).astype(np.int16)
