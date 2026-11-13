"""Pure stick-to-pointer math, independent of SDL, Qt and Windows."""
from __future__ import annotations

import math


def radial_deadzone(x: float, y: float, deadzone: float) -> tuple[float, float]:
    """Apply a circular deadzone and rescale the remaining range to [0, 1].

    Unlike a per-axis deadzone, small off-axis deflections are preserved, so
    diagonals do not snap to the horizontal or vertical axis.
    """
    deadzone = max(0.0, min(0.9, deadzone))
    magnitude = math.hypot(x, y)
    if magnitude <= deadzone:
        return 0.0, 0.0
    scaled = min(1.0, (magnitude - deadzone) / (1 - deadzone))
    return x / magnitude * scaled, y / magnitude * scaled


class SubpixelAccumulator:
    """Carry fractional pixels across ticks so slow movements are not lost."""

    def __init__(self) -> None:
        self.x = 0.0
        self.y = 0.0

    def take(self, dx: float, dy: float) -> tuple[int, int]:
        self.x += dx
        self.y += dy
        whole_x, whole_y = int(self.x), int(self.y)
        self.x -= whole_x
        self.y -= whole_y
        return whole_x, whole_y

    def reset(self) -> None:
        self.x = self.y = 0.0
