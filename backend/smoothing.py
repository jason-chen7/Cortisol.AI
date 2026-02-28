"""
smoothing.py — Exponential moving average for stress score stabilisation.
"""

from collections import deque


class EMASmoothing:
    """
    Exponential moving average across a rolling history window.

    Args:
        window: maximum history length (for introspection / future use)
        alpha:  EMA weight for the newest value (0 < alpha ≤ 1)
    """

    def __init__(self, window: int = 3, alpha: float = 0.5) -> None:
        self.window = window
        self.alpha = alpha
        self._history: deque[float] = deque(maxlen=window)
        self._ema: float | None = None

    def update(self, value: float) -> float:
        """Feed a new raw score and return the smoothed value."""
        self._history.append(value)
        if self._ema is None:
            self._ema = value
        else:
            self._ema = self.alpha * value + (1.0 - self.alpha) * self._ema
        return self._ema

    def reset(self) -> None:
        self._history.clear()
        self._ema = None

    @property
    def current(self) -> float | None:
        return self._ema
