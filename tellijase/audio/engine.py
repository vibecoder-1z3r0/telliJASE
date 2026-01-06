"""Simple AY-3-8914 PCM generator for JAM previews."""

from __future__ import annotations

import numpy as np

from tellijase.psg.utils import CLOCK_HZ, frequency_to_period, period_to_frequency, volume_to_amplitude


class AY38914Synth:
    """Generates PCM audio for a static AY register snapshot."""

    def __init__(self, sample_rate: int = 44_100) -> None:
        self.sample_rate = sample_rate

    def render(self, registers: dict[str, int], duration: float = 1.5) -> np.ndarray:
        """Render a mono PCM buffer from the provided registers."""

        num_samples = max(1, int(self.sample_rate * duration))
        t = np.arange(num_samples, dtype=np.float64) / self.sample_rate
        mix = np.zeros(num_samples, dtype=np.float64)

        # tone channels A/B/C
        channels = [
            ("R0", "R1", "R8"),
            ("R2", "R3", "R9"),
            ("R4", "R5", "R10"),
        ]
        for fine_reg, coarse_reg, vol_reg in channels:
            period = self._read_period(registers, fine_reg, coarse_reg)
            freq = period_to_frequency(period)
            volume = volume_to_amplitude(registers.get(vol_reg, 0))
            if freq <= 0 or volume <= 0:
                continue
            wave = self._square_wave(freq, t)
            mix += wave * volume

        # crude noise approximation using shared period + volume from channel C
        noise_period = registers.get("R6", 0)
        noise_volume = volume_to_amplitude(registers.get("R10", 0))
        if noise_period > 0 and noise_volume > 0:
            noise = self._noise_wave(noise_period, num_samples)
            mix += noise * noise_volume * 0.5

        max_val = np.max(np.abs(mix)) or 1.0
        mix = np.clip(mix / max_val, -1.0, 1.0)
        return mix.astype(np.float32)

    @staticmethod
    def _square_wave(freq: float, t: np.ndarray) -> np.ndarray:
        phase = (freq * t) % 1.0
        return np.where(phase < 0.5, 1.0, -1.0)

    @staticmethod
    def _noise_wave(period: int, length: int) -> np.ndarray:
        rng = np.random.default_rng(seed=period)
        return rng.uniform(-1.0, 1.0, size=length)

    @staticmethod
    def _read_period(registers: dict[str, int], fine_reg: str, coarse_reg: str) -> int:
        fine = registers.get(fine_reg, 0)
        coarse = registers.get(coarse_reg, 0) & 0x0F
        period = (coarse << 8) | fine
        return max(1, period)


__all__ = ["AY38914Synth", "frequency_to_period", "period_to_frequency"]
