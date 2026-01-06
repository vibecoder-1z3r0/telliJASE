"""Utilities for AY-3-8914 frequency conversions."""

from __future__ import annotations

CLOCK_HZ = 3_579_545  # NTSC color subcarrier used by Intellivision PSG
MIN_PERIOD = 1
MAX_PERIOD = 1023


def period_to_frequency(period: int) -> float:
    if period <= 0:
        return 0.0
    return CLOCK_HZ / (16.0 * period)


def frequency_to_period(freq: float) -> int:
    if freq <= 0:
        return MAX_PERIOD
    period = int(round(CLOCK_HZ / (16.0 * freq)))
    return max(MIN_PERIOD, min(MAX_PERIOD, period))


def volume_to_amplitude(volume: int) -> float:
    volume = max(0, min(15, int(volume)))
    return volume / 15.0
