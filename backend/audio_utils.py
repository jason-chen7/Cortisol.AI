"""
audio_utils.py — PCM conversion and sliding-window buffering.
"""

import numpy as np
import torch

SAMPLE_RATE = 16_000


def pcm16_to_float32(raw_bytes: bytes) -> np.ndarray:
    """Convert raw little-endian 16-bit PCM bytes → float32 in [-1, 1]."""
    audio_int16 = np.frombuffer(raw_bytes, dtype=np.int16)
    return audio_int16.astype(np.float32) / 32_768.0


def float32_to_tensor(audio_np: np.ndarray) -> torch.Tensor:
    return torch.tensor(audio_np, dtype=torch.float32)


class SlidingWindowBuffer:
    """
    Accumulates float32 audio samples and yields fixed-size windows
    with the configured stride.

    Attributes:
        window_size:      samples per analysis window
        stride:           samples advanced per step
        consumed_samples: total samples removed from the front so far
                          → start_time = consumed_samples / SAMPLE_RATE
    """

    def __init__(
        self,
        window_size_sec: float = 1.5,
        stride_sec: float = 0.75,
        sample_rate: int = SAMPLE_RATE,
    ) -> None:
        self.window_size = int(window_size_sec * sample_rate)
        self.stride = int(stride_sec * sample_rate)
        self.sample_rate = sample_rate
        self._buf = np.array([], dtype=np.float32)
        self.consumed_samples = 0

    def add(self, chunk: np.ndarray) -> None:
        self._buf = np.concatenate([self._buf, chunk])

    def get_windows(self) -> list[tuple[int, np.ndarray]]:
        """
        Returns list of (start_sample, window_array).
        Advances internal buffer by stride after each window.
        """
        windows: list[tuple[int, np.ndarray]] = []
        while len(self._buf) >= self.window_size:
            window = self._buf[: self.window_size].copy()
            windows.append((self.consumed_samples, window))
            self._buf = self._buf[self.stride :]
            self.consumed_samples += self.stride
        return windows

    def reset(self) -> None:
        self._buf = np.array([], dtype=np.float32)
        self.consumed_samples = 0
