"""Utilities for AY-3-8914 frequency conversions.

Based on jzintv documentation:
http://spatula-city.org/~im14u2c/intv/jzintv-1.0-beta3/doc/programming/psg.txt

The PSG divides the input clock by 32 total:
  - First divides by 16 internally
  - Then divides by the Period register value
"""

from __future__ import annotations

# NTSC Intellivision clock (PAL uses 4.0 MHz)
CLOCK_HZ = 3_579_545  # NTSC color subcarrier / 2 (fed to PSG)

MIN_PERIOD = 1
MAX_PERIOD = 4095  # 12-bit period register


def period_to_frequency(period: int) -> float:
    """Convert PSG period value to frequency in Hz.

    Formula: F = CLOCK_HZ / (32 × Period)
    """
    if period <= 0:
        return 0.0
    return CLOCK_HZ / (32.0 * period)


def frequency_to_period(freq: float) -> int:
    """Convert frequency in Hz to PSG period value.

    Formula: Period = CLOCK_HZ / (32 × F)
    """
    if freq <= 0:
        return MAX_PERIOD
    period = int(round(CLOCK_HZ / (32.0 * freq)))
    return max(MIN_PERIOD, min(MAX_PERIOD, period))


def volume_to_amplitude(volume: int) -> float:
    volume = max(0, min(15, int(volume)))
    return volume / 15.0
