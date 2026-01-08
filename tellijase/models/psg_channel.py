"""PSGChannel model - represents one AY-3-8914 channel."""

from __future__ import annotations

from dataclasses import dataclass

from ..psg.utils import frequency_to_period


@dataclass
class PSGChannel:
    """Domain model for one AY-3-8914 tone channel.

    This represents the user-facing parameters (frequency in Hz, volume 0-15,
    mixer enables) rather than low-level register values.
    """

    frequency: float = 440.0        # Hz (will be clamped to valid range)
    volume: int = 12                # 0-15
    tone_enabled: bool = True       # R7 mixer bit for tone
    noise_enabled: bool = False     # R7 mixer bit for noise
    envelope_mode: bool = False     # Use envelope generator for volume

    def __post_init__(self) -> None:
        """Validate and clamp parameters to valid ranges."""
        self.frequency = max(27.0, min(20000.0, self.frequency))
        self.volume = max(0, min(15, int(self.volume)))

    def to_registers(self, channel_index: int) -> dict[str, int]:
        """Convert to AY-3-8914 register values.

        Args:
            channel_index: 0 for channel A, 1 for B, 2 for C

        Returns:
            Dict with register names (R0, R1, R8, etc.) and values
        """
        period = frequency_to_period(self.frequency)

        # Register offsets based on channel
        # Channel A: R0/R1 (period), R10 (volume)
        # Channel B: R2/R3 (period), R11 (volume)
        # Channel C: R4/R5 (period), R12 (volume)
        period_reg_base = channel_index * 2
        volume_reg = 10 + channel_index

        fine_reg = f"R{period_reg_base}"
        coarse_reg = f"R{period_reg_base + 1}"
        vol_reg = f"R{volume_reg}"

        # Volume byte: bits 0-3 = volume, bit 4 = envelope mode
        volume_byte = self.volume & 0x0F
        if self.envelope_mode:
            volume_byte |= 0x10  # Set M bit

        return {
            fine_reg: period & 0xFF,
            coarse_reg: (period >> 8) & 0x0F,
            vol_reg: volume_byte,
        }

    @classmethod
    def from_registers(
        cls,
        fine: int,
        coarse: int,
        volume_byte: int,
    ) -> PSGChannel:
        """Deserialize from register values.

        Args:
            fine: Fine period byte (R0/R2/R4)
            coarse: Coarse period byte (R1/R3/R5)
            volume_byte: Volume/envelope byte (R10/R11/R12)

        Returns:
            PSGChannel instance
        """
        from ..psg.utils import period_to_frequency

        period = (coarse & 0x0F) << 8 | fine
        frequency = period_to_frequency(period)
        volume = volume_byte & 0x0F
        envelope_mode = bool(volume_byte & 0x10)

        # Note: tone_enabled and noise_enabled come from R7, handled by PSGState
        return cls(
            frequency=frequency,
            volume=volume,
            envelope_mode=envelope_mode,
        )


__all__ = ["PSGChannel"]
