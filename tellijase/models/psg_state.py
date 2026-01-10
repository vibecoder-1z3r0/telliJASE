"""PSGState model - complete AY-3-8914 state."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict

from .psg_channel import PSGChannel


@dataclass
class PSGState:
    """Complete AY-3-8914 state - single source of truth for all PSG parameters.

    This is the model that both the UI and audio engine interact with.
    It maintains high-level parameters and converts to register values on demand.
    """

    channel_a: PSGChannel = field(default_factory=PSGChannel)
    channel_b: PSGChannel = field(default_factory=PSGChannel)
    channel_c: PSGChannel = field(default_factory=PSGChannel)

    noise_period: int = 1  # R6 (0-31) - Start at 1 so noise is ready to use
    envelope_period: int = 0  # R13/R14 (0-65535)
    envelope_shape: int = 0  # R15 (0-15)

    def __post_init__(self) -> None:
        """Validate and clamp parameters."""
        self.noise_period = max(0, min(31, int(self.noise_period)))
        self.envelope_period = max(0, min(65535, int(self.envelope_period)))
        self.envelope_shape = max(0, min(15, int(self.envelope_shape)))

    def to_registers(self) -> Dict[str, int]:
        """Flatten to R0-R15 register map for audio synthesis.

        Returns:
            Dict with keys like 'R0', 'R1', etc. and integer values
        """
        regs: Dict[str, int] = {}

        # Channels A, B, C - period and volume registers
        regs.update(self.channel_a.to_registers(0))
        regs.update(self.channel_b.to_registers(1))
        regs.update(self.channel_c.to_registers(2))

        # R7 mixer control (inverted logic: 0=enable, 1=disable)
        # Bit 0: Channel A tone
        # Bit 1: Channel B tone
        # Bit 2: Channel C tone
        # Bit 3: Channel A noise
        # Bit 4: Channel B noise
        # Bit 5: Channel C noise
        # Bits 6-7: I/O (unused on Intellivision)
        r7 = 0xFF  # Start with all disabled

        if self.channel_a.tone_enabled:
            r7 &= ~0x01
        if self.channel_b.tone_enabled:
            r7 &= ~0x02
        if self.channel_c.tone_enabled:
            r7 &= ~0x04
        if self.channel_a.noise_enabled:
            r7 &= ~0x08
        if self.channel_b.noise_enabled:
            r7 &= ~0x10
        if self.channel_c.noise_enabled:
            r7 &= ~0x20

        regs["R7"] = r7

        # R6 noise period
        regs["R6"] = self.noise_period & 0x1F

        # R13/R14 envelope period (16-bit)
        regs["R13"] = self.envelope_period & 0xFF
        regs["R14"] = (self.envelope_period >> 8) & 0xFF

        # R15 envelope shape
        regs["R15"] = self.envelope_shape & 0x0F

        return regs

    def snapshot(self) -> PSGState:
        """Create thread-safe immutable copy for audio thread.

        Returns:
            Deep copy of this PSGState
        """
        return replace(
            self,
            channel_a=replace(self.channel_a),
            channel_b=replace(self.channel_b),
            channel_c=replace(self.channel_c),
        )

    @classmethod
    def from_registers(cls, registers: Dict[str, int]) -> PSGState:
        """Deserialize from register dict (for loading projects).

        Args:
            registers: Dict with keys like 'R0', 'R1', etc.

        Returns:
            PSGState instance
        """
        # Reconstruct channels
        channel_a = PSGChannel.from_registers(
            registers.get("R0", 0),
            registers.get("R1", 0),
            registers.get("R10", 0),
        )
        channel_b = PSGChannel.from_registers(
            registers.get("R2", 0),
            registers.get("R3", 0),
            registers.get("R11", 0),
        )
        channel_c = PSGChannel.from_registers(
            registers.get("R4", 0),
            registers.get("R5", 0),
            registers.get("R12", 0),
        )

        # Decode R7 mixer (inverted logic)
        r7 = registers.get("R7", 0xFF)
        channel_a.tone_enabled = not bool(r7 & 0x01)
        channel_b.tone_enabled = not bool(r7 & 0x02)
        channel_c.tone_enabled = not bool(r7 & 0x04)
        channel_a.noise_enabled = not bool(r7 & 0x08)
        channel_b.noise_enabled = not bool(r7 & 0x10)
        channel_c.noise_enabled = not bool(r7 & 0x20)

        # Noise and envelope
        noise_period = registers.get("R6", 0) & 0x1F
        envelope_period = (registers.get("R14", 0) << 8) | registers.get("R13", 0)
        envelope_shape = registers.get("R15", 0) & 0x0F

        return cls(
            channel_a=channel_a,
            channel_b=channel_b,
            channel_c=channel_c,
            noise_period=noise_period,
            envelope_period=envelope_period,
            envelope_shape=envelope_shape,
        )


__all__ = ["PSGState"]
