import numpy as np

from tellijase.audio.engine import AY38914Synth
from tellijase.psg.utils import frequency_to_period, period_to_frequency


def test_frequency_period_roundtrip():
    freq = 440.0
    period = frequency_to_period(freq)
    recon = period_to_frequency(period)
    assert abs(recon - freq) / freq < 0.05  # within 5%


def test_synth_generates_audio():
    synth = AY38914Synth(sample_rate=8000)
    registers = {"R0": 0xFE, "R1": 0x00, "R8": 15}
    buffer = synth.render(registers, duration=0.1)
    assert buffer.ndim == 1
    assert len(buffer) == 800
    assert np.max(np.abs(buffer)) <= 1.0
