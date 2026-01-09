"""Pygame-based audio playback for WSL/environments where sounddevice fails."""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

try:
    import pygame.mixer

    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    pygame = None  # type: ignore

from ..models import PSGState
from .synthesizer import PSGSynthesizer

logger = logging.getLogger(__name__)


class PygamePSGPlayer:
    """Real-time PSG audio using pygame.mixer.

    This is a fallback for environments where sounddevice doesn't work (like WSL).
    Uses one-shot playback with very short buffers to approximate real-time response.
    """

    def __init__(
        self,
        psg_state: PSGState,
        sample_rate: int = 44100,
        buffer_size: int = 2048,
    ):
        """Initialize pygame audio player.

        Args:
            psg_state: PSG state to read parameters from
            sample_rate: Audio sample rate in Hz
            buffer_size: Audio buffer size in samples
        """
        self.psg_state = psg_state
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.synth = PSGSynthesizer(sample_rate)
        self.available = PYGAME_AVAILABLE
        self.playing = False

        if not self.available:
            logger.warning("pygame not available - audio disabled")
            return

        try:
            # Initialize pygame mixer
            pygame.mixer.init(
                frequency=sample_rate,
                size=-16,  # 16-bit signed
                channels=1,  # Mono
                buffer=buffer_size,
            )
            logger.info(f"PygamePSGPlayer initialized: {sample_rate}Hz, {buffer_size} samples")
        except Exception as e:
            logger.error(f"Failed to initialize pygame mixer: {e}")
            self.available = False

    def start(self) -> bool:
        """Start continuous audio playback.

        Note: pygame.mixer doesn't have true streaming callbacks, so we use
        a short buffer and queue the next buffer when the current one ends.

        Returns:
            True if started successfully
        """
        if not self.available:
            logger.warning("Cannot start - pygame not available")
            return False

        if self.playing:
            return True

        try:
            # Generate initial buffer
            state = self.psg_state.snapshot()
            samples = self.synth.render_buffer(self.buffer_size, state)

            # Convert to int16 for pygame
            pcm = self._to_int16(samples)

            # Create Sound object and play
            sound = pygame.mixer.Sound(buffer=pcm)
            sound.play(loops=-1)  # Loop continuously

            self.playing = True
            logger.info("Pygame audio started")
            return True

        except Exception as e:
            logger.error(f"Failed to start pygame audio: {e}")
            return False

    def stop(self) -> None:
        """Stop audio playback."""
        if self.available and self.playing:
            try:
                pygame.mixer.stop()
                self.playing = False
                logger.info("Pygame audio stopped")
            except Exception as e:
                logger.error(f"Error stopping pygame audio: {e}")

    def is_playing(self) -> bool:
        """Check if audio is currently playing.

        Returns:
            True if playing
        """
        return self.playing

    @staticmethod
    def _to_int16(samples: np.ndarray) -> np.ndarray:
        """Convert float32 samples to int16 for pygame.

        Args:
            samples: Float samples in range [-1.0, 1.0]

        Returns:
            Int16 samples
        """
        clipped = np.clip(samples, -1.0, 1.0)
        return (clipped * 32767).astype(np.int16)


__all__ = ["PygamePSGPlayer", "PYGAME_AVAILABLE"]
