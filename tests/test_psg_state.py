"""Tests for PSGState model with correct R7 mixer logic."""

from tellijase.models import PSGChannel, PSGState


def test_psg_state_default():
    """Test PSGState initializes with sensible defaults."""
    state = PSGState()

    assert state.channel_a.frequency == 440.0
    assert state.channel_a.volume == 12
    assert state.channel_a.tone_enabled is True
    assert state.channel_a.noise_enabled is False

    assert state.noise_period == 0
    assert state.envelope_period == 0
    assert state.envelope_shape == 0


def test_psg_state_to_registers():
    """Test PSGState correctly converts to register map with R7 mixer."""
    state = PSGState()
    state.channel_a.frequency = 440.0
    state.channel_a.volume = 12
    state.channel_a.tone_enabled = True
    state.channel_a.noise_enabled = False

    state.channel_b.frequency = 880.0
    state.channel_b.volume = 10
    state.channel_b.tone_enabled = True
    state.channel_b.noise_enabled = True  # Tone + noise mix

    state.channel_c.frequency = 220.0
    state.channel_c.volume = 8
    state.channel_c.tone_enabled = False
    state.channel_c.noise_enabled = True  # Noise only

    state.noise_period = 15

    regs = state.to_registers()

    # Check channel A period (440 Hz)
    period_a = (regs["R1"] << 8) | regs["R0"]
    assert period_a > 0  # Should have valid period

    # Check channel A volume
    assert regs["R10"] == 12

    # Check R7 mixer (inverted logic: 0=enable, 1=disable)
    r7 = regs["R7"]

    # Channel A: tone enabled (bit 0 = 0), noise disabled (bit 3 = 1)
    assert (r7 & 0x01) == 0  # Tone enabled
    assert (r7 & 0x08) != 0  # Noise disabled

    # Channel B: tone enabled (bit 1 = 0), noise enabled (bit 4 = 0)
    assert (r7 & 0x02) == 0  # Tone enabled
    assert (r7 & 0x10) == 0  # Noise enabled

    # Channel C: tone disabled (bit 2 = 1), noise enabled (bit 5 = 0)
    assert (r7 & 0x04) != 0  # Tone disabled
    assert (r7 & 0x20) == 0  # Noise enabled

    # Check noise period
    assert regs["R6"] == 15


def test_psg_state_snapshot():
    """Test PSGState snapshot creates independent copy."""
    state = PSGState()
    state.channel_a.frequency = 1000.0

    snapshot = state.snapshot()

    # Modify original
    state.channel_a.frequency = 2000.0

    # Snapshot should be unchanged
    assert snapshot.channel_a.frequency == 1000.0
    assert state.channel_a.frequency == 2000.0


def test_psg_state_from_registers():
    """Test PSGState can be deserialized from registers."""
    # Create initial state
    state1 = PSGState()
    state1.channel_a.frequency = 440.0
    state1.channel_a.volume = 12
    state1.channel_a.tone_enabled = True
    state1.channel_a.noise_enabled = False
    state1.noise_period = 10

    # Convert to registers
    regs = state1.to_registers()

    # Deserialize back
    state2 = PSGState.from_registers(regs)

    # Check values are approximately preserved
    assert abs(state2.channel_a.frequency - 440.0) < 10  # Allow some rounding
    assert state2.channel_a.volume == 12
    assert state2.channel_a.tone_enabled is True
    assert state2.channel_a.noise_enabled is False
    assert state2.noise_period == 10


def test_psg_channel_to_registers():
    """Test PSGChannel correctly converts to period/volume registers."""
    channel = PSGChannel(frequency=440.0, volume=15)

    regs = channel.to_registers(0)  # Channel A

    # Check registers exist
    assert "R0" in regs  # Fine period
    assert "R1" in regs  # Coarse period
    assert "R10" in regs  # Volume

    # Check volume
    assert (regs["R10"] & 0x0F) == 15

    # Check period is non-zero
    period = (regs["R1"] << 8) | regs["R0"]
    assert period > 0
