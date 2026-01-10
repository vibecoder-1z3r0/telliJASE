"""Pygame-based audio playback for WSL/environments where sounddevice fails."""

from __future__ import annotations

import logging
import threading
import time

import numpy as np

try:
    import pygame.mixer

    PYGAME_AVAILABLE = True
    # Detect if using pygame-ce (community edition)
    PYGAME_VERSION = getattr(pygame, "__version__", "unknown")
except ImportError:
    PYGAME_AVAILABLE = False
    PYGAME_VERSION = None
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
        buffer_size: int = 4096,  # Larger buffer for smoother playback
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
        self.channel = None
        self.update_thread = None
        self.stop_event = threading.Event()

        if not self.available:
            logger.warning("pygame not available - audio disabled")
            return

        try:
            # Initialize pygame mixer with smaller system buffer for lower latency
            pygame.mixer.init(
                frequency=sample_rate,
                size=-16,  # 16-bit signed
                channels=1,  # Mono
                buffer=1024,  # System buffer (not our generation buffer)
            )
            # Reserve a channel for our audio
            pygame.mixer.set_num_channels(1)
            self.channel = pygame.mixer.Channel(0)
            logger.info(
                f"PygamePSGPlayer initialized: {sample_rate}Hz, "
                f"{buffer_size} samples (pygame {PYGAME_VERSION})"
            )
        except Exception as e:
            logger.error(f"Failed to initialize pygame mixer: {e}")
            self.available = False

    def _audio_update_loop(self) -> None:
        """Background thread that continuously regenerates and queues audio."""
        logger.debug("Audio update thread started")

        try:
            while not self.stop_event.is_set():
                # Check if channel has room in queue (queue() returns None if full)
                if self.channel.get_queue() is None:
                    # Generate fresh buffer with current PSG state
                    state = self.psg_state.snapshot()
                    samples = self.synth.render_buffer(self.buffer_size, state)
                    pcm = self._to_int16(samples)

                    # Create sound and queue it
                    sound = pygame.mixer.Sound(buffer=pcm)
                    self.channel.queue(sound)

                # Small sleep to avoid busy-waiting
                time.sleep(0.01)  # 10ms

        except Exception as e:
            logger.error(f"Error in audio update loop: {e}")
        finally:
            logger.debug("Audio update thread stopped")

    def start(self) -> bool:
        """Start continuous audio playback with real-time parameter updates.

        Uses a background thread to continuously regenerate audio based on
        current PSG state, allowing sliders to affect the sound in real-time.

        Returns:
            True if started successfully
        """
        if not self.available:
            logger.warning("Cannot start - pygame not available")
            return False

        if self.playing:
            return True

        try:
            # Generate and play initial buffer to start audio immediately
            state = self.psg_state.snapshot()
            samples = self.synth.render_buffer(self.buffer_size, state)
            pcm = self._to_int16(samples)
            sound = pygame.mixer.Sound(buffer=pcm)
            self.channel.play(sound)

            # Start background thread to continuously regenerate audio
            self.stop_event.clear()
            self.update_thread = threading.Thread(
                target=self._audio_update_loop, daemon=True, name="PygameAudioUpdate"
            )
            self.update_thread.start()

            self.playing = True
            logger.info("Pygame audio started with continuous regeneration")
            return True

        except Exception as e:
            logger.error(f"Failed to start pygame audio: {e}")
            return False

    def stop(self) -> None:
        """Stop audio playback and background thread."""
        if self.available and self.playing:
            try:
                # Signal thread to stop
                self.stop_event.set()

                # Wait for thread to finish (with timeout)
                if self.update_thread and self.update_thread.is_alive():
                    self.update_thread.join(timeout=1.0)

                # Stop audio
                if self.channel:
                    self.channel.stop()

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


__all__ = ["PygamePSGPlayer", "PYGAME_AVAILABLE", "PYGAME_VERSION"]
