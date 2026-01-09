"""PSG audio synthesis with correct per-channel tone+noise mixing."""

from __future__ import annotations

import numpy as np

from ..models import PSGState
from ..psg.utils import CLOCK_HZ, period_to_frequency


class PSGSynthesizer:
    """Generates PCM audio from PSGState - pure numpy, no Qt.

    Implements correct AY-3-8914 mixing:
    - Shared noise generator
    - Per-channel tone+noise mixing controlled by R7
    - Volume applied to MIXED signal per channel
    """

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate

        # Phase accumulators for continuity (prevents clicks on parameter changes)
        self.phase_a = 0.0
        self.phase_b = 0.0
        self.phase_c = 0.0
        self.noise_phase = 0.0

        # Noise LFSR state (17-bit)
        self.lfsr = 1
        self.lfsr_output = 1.0

    def render_buffer(self, num_samples: int, state: PSGState) -> np.ndarray:
        """Generate mono PCM samples from current PSG state.

        Args:
            num_samples: Number of samples to generate
            state: Current PSG state

        Returns:
            float32 array of samples in range [-1.0, 1.0]
        """
        regs = state.to_registers()
        r7 = regs.get("R7", 0xFF)

        # Generate shared noise waveform (used by all channels)
        noise = self._generate_noise(num_samples, regs.get("R6", 0))

        # Initialize mix buffer
        mix = np.zeros(num_samples, dtype=np.float32)

        # Process each channel with correct per-channel mixing
        channels = [
            (0, "R0", "R1", "R10", 0x01, 0x08, self.phase_a),  # Channel A
            (1, "R2", "R3", "R11", 0x02, 0x10, self.phase_b),  # Channel B
            (2, "R4", "R5", "R12", 0x04, 0x20, self.phase_c),  # Channel C
        ]

        for idx, fine_r, coarse_r, vol_r, tone_bit, noise_bit, phase in channels:
            # Check mixer enables (R7 uses inverted logic: 0=enabled, 1=disabled)
            tone_enabled = not bool(r7 & tone_bit)
            noise_enabled = not bool(r7 & noise_bit)

            if not tone_enabled and not noise_enabled:
                continue  # Channel fully muted

            # Hardware-accurate digital AND gating
            # PSG treats tone/noise as digital signals (HIGH/LOW) and uses AND logic
            if tone_enabled and noise_enabled:
                # Both enabled: AND gate (output HIGH only when both are HIGH)
                period = self._read_period(regs, fine_r, coarse_r)
                freq = period_to_frequency(period)
                if freq > 0:
                    tone, new_phase = self._generate_tone(num_samples, freq, phase)

                    # Update phase accumulator
                    if idx == 0:
                        self.phase_a = new_phase
                    elif idx == 1:
                        self.phase_b = new_phase
                    else:
                        self.phase_c = new_phase

                    # Digital AND: output is +1 only when BOTH tone and noise are +1
                    channel_signal = np.where((tone > 0) & (noise > 0), 1.0, -1.0).astype(np.float32)
                else:
                    channel_signal = noise
            elif tone_enabled:
                # Tone only
                period = self._read_period(regs, fine_r, coarse_r)
                freq = period_to_frequency(period)
                if freq > 0:
                    tone, new_phase = self._generate_tone(num_samples, freq, phase)
                    channel_signal = tone

                    # Update phase accumulator
                    if idx == 0:
                        self.phase_a = new_phase
                    elif idx == 1:
                        self.phase_b = new_phase
                    else:
                        self.phase_c = new_phase
                else:
                    channel_signal = np.zeros(num_samples, dtype=np.float32)
            else:
                # Noise only
                channel_signal = noise

            # Apply volume to MIXED signal (this is the key!)
            volume = regs.get(vol_r, 0) & 0x0F
            amplitude = volume / 15.0
            mix += channel_signal * amplitude

        # Normalize to prevent clipping
        max_val = np.max(np.abs(mix))
        if max_val > 1.0:
            mix = mix / max_val

        return np.clip(mix, -1.0, 1.0).astype(np.float32)

    def _generate_tone(
        self, num_samples: int, freq: float, phase: float
    ) -> tuple[np.ndarray, float]:
        """Generate square wave with phase continuity.

        Args:
            num_samples: Number of samples to generate
            freq: Frequency in Hz
            phase: Current phase (0.0-1.0)

        Returns:
            Tuple of (waveform array, new phase)
        """
        if freq <= 0:
            return np.zeros(num_samples, dtype=np.float32), phase

        phase_increment = freq / self.sample_rate
        phases = np.arange(num_samples, dtype=np.float32) * phase_increment + phase

        # Square wave: phase < 0.5 = high, >= 0.5 = low
        wave = np.where((phases % 1.0) < 0.5, 1.0, -1.0).astype(np.float32)

        # Update phase for next buffer
        new_phase = (phases[-1] + phase_increment) % 1.0

        return wave, new_phase

    def _generate_noise(self, num_samples: int, period: int) -> np.ndarray:
        """Generate pseudo-random noise using LFSR.

        The AY-3-8914 uses a 17-bit LFSR for noise generation.
        For now, we use a simplified approach with numpy random.

        Args:
            num_samples: Number of samples to generate
            period: Noise period register value (0-31)

        Returns:
            Noise waveform array
        """
        if period == 0:
            return np.zeros(num_samples, dtype=np.float32)

        # Calculate noise frequency
        noise_freq = CLOCK_HZ / (32.0 * period) if period > 0 else 0

        if noise_freq <= 0:
            return np.zeros(num_samples, dtype=np.float32)

        # Simplified noise: update LFSR at noise frequency
        samples_per_update = max(1, int(self.sample_rate / noise_freq))

        noise = np.zeros(num_samples, dtype=np.float32)
        for i in range(0, num_samples, samples_per_update):
            # Simple 17-bit LFSR (taps at bits 17 and 14)
            bit = ((self.lfsr >> 0) ^ (self.lfsr >> 3)) & 1
            self.lfsr = (self.lfsr >> 1) | (bit << 16)
            self.lfsr_output = 1.0 if (self.lfsr & 1) else -1.0

            # Fill samples until next update
            end = min(i + samples_per_update, num_samples)
            noise[i:end] = self.lfsr_output

        return noise

    @staticmethod
    def _read_period(regs: dict, fine_r: str, coarse_r: str) -> int:
        """Read 12-bit period from fine and coarse registers.

        Args:
            regs: Register dict
            fine_r: Fine period register name (e.g., 'R0')
            coarse_r: Coarse period register name (e.g., 'R1')

        Returns:
            12-bit period value (1-4095)
        """
        fine = regs.get(fine_r, 0) & 0xFF
        coarse = regs.get(coarse_r, 0) & 0x0F
        period = (coarse << 8) | fine
        return max(1, period)


__all__ = ["PSGSynthesizer"]
