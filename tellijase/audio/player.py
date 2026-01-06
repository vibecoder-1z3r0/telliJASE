"""Qt audio playback utilities for JAM mode."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QByteArray, QBuffer, QObject, QIODevice
from PySide6.QtMultimedia import QAudioFormat, QAudioSink

from .engine import AY38914Synth


@dataclass
class JamAudioSettings:
    sample_rate: int = 44_100
    duration_seconds: float = 1.5


class JamAudioPlayer(QObject):
    """Wraps QAudioSink to play rendered AY samples."""

    def __init__(self, parent: QObject | None = None, settings: JamAudioSettings | None = None) -> None:
        super().__init__(parent)
        self.settings = settings or JamAudioSettings()
        self.synth = AY38914Synth(sample_rate=self.settings.sample_rate)

        fmt = QAudioFormat()
        fmt.setSampleRate(self.settings.sample_rate)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.Int16)

        self.audio_sink = QAudioSink(fmt, self)
        self.buffer = QBuffer()
        self.data = QByteArray()

    def play(self, registers: dict[str, int]) -> None:
        samples = self.synth.render(registers, self.settings.duration_seconds)
        pcm = self._to_int16(samples)
        self.data = QByteArray(pcm.tobytes())
        if self.buffer.isOpen():
            self.buffer.close()
        self.buffer.setData(self.data)
        self.buffer.open(QIODevice.ReadOnly)
        self.audio_sink.stop()
        self.audio_sink.start(self.buffer)

    def stop(self) -> None:
        self.audio_sink.stop()
        if self.buffer.isOpen():
            self.buffer.close()

    @staticmethod
    def _to_int16(samples: np.ndarray) -> np.ndarray:
        clipped = np.clip(samples, -1.0, 1.0)
        return (clipped * 32767).astype(np.int16)
