"""Real-time audio streaming using sounddevice."""

from __future__ import annotations

import logging
from typing import Optional

try:
    import sounddevice as sd

    SOUNDDEVICE_AVAILABLE = True
except (ImportError, OSError):
    SOUNDDEVICE_AVAILABLE = False
    sd = None  # type: ignore

from ..models import PSGState
from .synthesizer import PSGSynthesizer

logger = logging.getLogger(__name__)


class LivePSGStream:
    """Real-time PSG audio streaming with sounddevice.

    This provides continuous audio output that responds immediately to
    parameter changes in the PSGState. The audio callback runs in a
    separate thread managed by sounddevice.
    """

    def __init__(
        self,
        psg_state: PSGState,
        sample_rate: int = 44100,
        block_size: int = 2048,
    ):
        """Initialize the live audio stream.

        Args:
            psg_state: PSG state to read parameters from
            sample_rate: Audio sample rate in Hz
            block_size: Audio buffer size in samples (~46ms @ 44.1kHz)
        """
        self.psg_state = psg_state
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.synth = PSGSynthesizer(sample_rate)
        self.stream: Optional[sd.OutputStream] = None  # type: ignore
        self.available = SOUNDDEVICE_AVAILABLE

        if not self.available:
            logger.warning(
                "sounddevice not available - audio streaming disabled. "
                "Install with: pip install sounddevice"
            )
        else:
            logger.info(f"LivePSGStream initialized: {sample_rate}Hz, {block_size} samples")

    def _callback(
        self,
        outdata: sd.ndarray,
        frames: int,
        time: sd.CallbackFlags,
        status: sd.CallbackFlags,
    ) -> None:  # type: ignore
        """Audio callback - called by sounddevice thread to generate samples.

        This runs in a separate thread. It takes a snapshot of the current
        PSG state and generates audio samples on demand.

        Args:
            outdata: Output buffer to fill
            frames: Number of frames requested
            time: Timing information
            status: Status flags (errors, etc.)
        """
        if status:
            logger.warning(f"Audio callback status: {status}")

        try:
            # Thread-safe snapshot of current state
            state = self.psg_state.snapshot()

            # Generate samples with phase continuity
            samples = self.synth.render_buffer(frames, state)

            # Write to output (sounddevice expects Nx1 shape for mono)
            outdata[:] = samples.reshape(-1, 1)

        except Exception as e:
            logger.error(f"Error in audio callback: {e}")
            # Fill with silence on error
            outdata.fill(0)

    def _find_output_device(self):
        """Find a valid output audio device.

        Returns:
            Device ID or None to let sounddevice choose
        """
        device = None
        try:
            # Try to get default output device
            default_out = sd.default.device[1]
            if default_out is not None and default_out >= 0:
                device = default_out
        except (AttributeError, IndexError, TypeError):
            pass

        # If no valid default, find first available output device
        if device is None:
            devices = sd.query_devices()
            for idx, dev in enumerate(devices):
                if dev["max_output_channels"] > 0:
                    device = idx
                    logger.info(f"Using first available output device: {dev['name']}")
                    break

        return device

    def start(self) -> bool:
        """Start continuous audio playback.

        Returns:
            True if started successfully, False otherwise
        """
        if not self.available:
            logger.warning("Cannot start stream - sounddevice not available")
            return False

        if self.stream is not None:
            logger.warning("Stream already running")
            return True

        try:
            device = self._find_output_device()
            self.stream = sd.OutputStream(
                device=device,  # None is ok - lets sounddevice choose
                channels=1,
                samplerate=self.sample_rate,
                callback=self._callback,
                blocksize=self.block_size,
            )
            self.stream.start()
            logger.info(f"Audio stream started on device {device}")
            return True

        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}")
            self.stream = None
            return False

    def stop(self) -> None:
        """Stop audio playback."""
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
                logger.info("Audio stream stopped")
            except Exception as e:
                logger.error(f"Error stopping stream: {e}")
            finally:
                self.stream = None

    def is_playing(self) -> bool:
        """Check if stream is currently playing.

        Returns:
            True if stream is active
        """
        return self.stream is not None and self.stream.active


__all__ = ["LivePSGStream", "SOUNDDEVICE_AVAILABLE"]
