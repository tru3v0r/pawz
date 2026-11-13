"""Sticky cursor magnetism: approach, capture, hold with an escape threshold, release.

Pure geometry and state: no Windows calls. ``Magnet.step`` receives the cursor
position, the requested movement and the targets around, and returns what to do:
a relative movement, a warp onto a target, and optionally an event ("captured" or
"released") that the caller turns into controller haptics.

Behaviour
- Approach: targets ahead of the movement pull the cursor (continuous pull, per
  second whatever the polling rate); one within the snap radius captures it.
- Hold: a captured cursor stays on its target. The stick movement is accumulated
  instead of applied; once it exceeds the escape threshold the cursor is released
  just outside the capture zone, in the direction of the effort (the accumulated
  effort itself can be hundreds of pixels and is not applied). The threshold is a push duration at
  full stick deflection (``ESCAPE_MIN_S`` to ``ESCAPE_MIN_S + ESCAPE_RANGE_S``
  seconds with strength), converted to pixels with the pointer's full speed so the
  effort feels the same whatever the speed setting. On a window edge, movement along the
  edge glides freely and only the perpendicular effort counts.
- Spatial navigation: points sharing a ``group`` (the caption buttons of a window)
  form a row. Pushing sideways from one of them jumps straight onto the next one in
  that direction, centred, without any escape effort; holding the push keeps
  navigating every ``NAV_REPEAT`` seconds. Past the last one, the push escapes as
  usual. Likewise, held on an edge, pushing across it toward a button within
  ``NAV_REACH`` (from the right edge near the top, or the top edge near the right)
  jumps onto the closest such button.
- Release: the released target cannot capture again until the cursor has moved
  away from it, so leaving never bounces back.
- Without movement for ``IDLE_RESET`` seconds the escape effort is forgotten.
"""
from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import NamedTuple

PULL_RADIUS = 110.0
SNAP_RADIUS = 40.0
ESCAPE_MIN_S = 0.06
ESCAPE_RANGE_S = 0.34
DEFAULT_FULL_SPEED = 960.0  # px/s at full deflection with the default speed (16 x 60)
IDLE_RESET = 0.15
SAME_TARGET = 2.0
NAV_REPEAT = 0.3
NAV_REACH = 80.0


class Target(NamedTuple):
    """A point, or a window edge given as the cursor's projection onto it."""
    x: float
    y: float
    kind: str = "point"  # "point" | "hline" (horizontal edge) | "vline" (vertical edge)
    lo: float = 0.0  # extent along the edge (edges only)
    hi: float = 0.0
    group: str = ""  # points of one row (caption buttons of a window)


@dataclass(frozen=True)
class MagnetStep:
    delta: tuple[float, float] = (0.0, 0.0)
    warp: tuple[int, int] | None = None
    event: str | None = None  # "captured" | "released"


def escape_threshold(strength: float, full_speed: float = DEFAULT_FULL_SPEED) -> float:
    """Pixels of stick movement needed to leave a target; ``strength`` is 0-1."""
    return max(1.0, full_speed) * (ESCAPE_MIN_S + ESCAPE_RANGE_S * strength)


def as_target(target) -> Target:
    return target if isinstance(target, Target) else Target(float(target[0]), float(target[1]))


def pull_delta(dx: float, dy: float, cursor: tuple[float, float], targets: list,
               strength: float, time_scale: float = 1.0) -> tuple[float, float]:
    """Bend the movement toward the nearest target. ``strength`` is 0-100 and the
    pull was tuned per 60 Hz frame; ``time_scale`` (elapsed time x 60) keeps it per second."""
    strength = max(0.0, min(100.0, strength)) / 100
    if not strength or not targets:
        return dx, dy
    nearest = min((as_target(t) for t in targets), key=lambda t: math.dist(cursor, (t.x, t.y)))
    distance = math.dist(cursor, (nearest.x, nearest.y))
    if distance >= PULL_RADIUS:
        return dx, dy
    pull = min(1.0, 0.035 * strength * (1 - distance / PULL_RADIUS) * time_scale)
    return dx + (nearest.x - cursor[0]) * pull, dy + (nearest.y - cursor[1]) * pull


def _snap_candidate(cursor: tuple[float, float], dx: float, dy: float,
                    targets: list[Target], radius: float) -> Target | None:
    """Target closest to the movement segment, within ``radius``."""
    length_squared = dx * dx + dy * dy
    best, best_distance = None, radius
    for target in targets:
        progress = ((target.x - cursor[0]) * dx + (target.y - cursor[1]) * dy) / length_squared
        if progress <= 0:
            continue
        progress = min(1.0, progress)
        distance = math.hypot(target.x - (cursor[0] + progress * dx),
                              target.y - (cursor[1] + progress * dy))
        if distance <= best_distance:
            best, best_distance = target, distance
    return best


def _distance_to(target: Target, cursor: tuple[float, float]) -> float:
    if target.kind == "hline":
        return abs(cursor[1] - target.y)
    if target.kind == "vline":
        return abs(cursor[0] - target.x)
    return math.dist(cursor, (target.x, target.y))


def _same(a: Target, b: Target) -> bool:
    if a.kind != b.kind:
        return False
    if a.kind == "hline":
        return abs(a.y - b.y) <= SAME_TARGET
    if a.kind == "vline":
        return abs(a.x - b.x) <= SAME_TARGET
    return math.dist((a.x, a.y), (b.x, b.y)) <= SAME_TARGET


def _button_across_edge(captured: Target, cursor, dx: float, dy: float,
                        found: list[Target]) -> Target | None:
    """Closest grouped point within reach on the side the push crosses the edge to."""
    if captured.kind == "vline" and abs(dx) > abs(dy):
        axis, push = 0, dx
    elif captured.kind == "hline" and abs(dy) > abs(dx):
        axis, push = 1, dy
    else:
        return None
    reachable = [t for t in found
                 if t.kind == "point" and t.group
                 and ((t.x, t.y)[axis] - cursor[axis]) * push > 0
                 and abs(t.x - cursor[0]) <= NAV_REACH and abs(t.y - cursor[1]) <= NAV_REACH]
    return min(reachable, key=lambda t: math.dist(cursor, (t.x, t.y)), default=None)


def _neighbour(captured: Target, dx: float, found: list[Target]) -> Target | None:
    """Closest point of the same row on the side ``dx`` points to."""
    side = [t for t in found
            if t.kind == "point" and t.group == captured.group
            and (t.x - captured.x) * dx > SAME_TARGET]
    return min(side, key=lambda t: abs(t.x - captured.x), default=None)


class Magnet:
    def __init__(self) -> None:
        self.captured: Target | None = None
        self.ignored: Target | None = None
        self.escape = [0.0, 0.0]
        self.last_step = -math.inf
        self.nav_ready = -math.inf

    def reset(self) -> None:
        self.__init__()

    def step(self, cursor: tuple[float, float], dx: float, dy: float, strength: float,
             targets: Iterable, now: float, time_scale: float = 1.0,
             full_speed: float = DEFAULT_FULL_SPEED) -> MagnetStep:
        """``full_speed``: cursor speed in px/s at full stick deflection."""
        s = max(0.0, min(100.0, strength)) / 100
        if not s:
            self.reset()
            return MagnetStep((dx, dy))
        if now - self.last_step > IDLE_RESET:
            self.escape = [0.0, 0.0]
            self.nav_ready = -math.inf
        self.last_step = now
        found = [as_target(t) for t in targets]
        snap_radius = SNAP_RADIUS * s
        if self.ignored is not None and _distance_to(self.ignored, cursor) > snap_radius + SAME_TARGET:
            self.ignored = None
        if self.captured is not None:
            return self._hold(cursor, dx, dy, escape_threshold(s, full_speed),
                              snap_radius, found, now)
        return self._approach(cursor, dx, dy, strength, snap_radius, found, time_scale)

    def _hold(self, cursor, dx, dy, threshold: float, snap_radius: float,
              found: list[Target], now: float) -> MagnetStep:
        captured = self.captured
        assert captured is not None
        still_there = any(_same(captured, target) for target in found)
        if not still_there or _distance_to(captured, cursor) > SAME_TARGET + 1:
            # Target vanished (window moved/closed) or the cursor was moved by
            # another device: let go without ceremony.
            self.captured = None
            return MagnetStep((dx, dy))
        if captured.kind == "point":
            destination = (_neighbour(captured, dx, found)
                           if captured.group and abs(dx) > abs(dy) else None)
        else:
            destination = _button_across_edge(captured, cursor, dx, dy, found)
        if destination is not None:
            self.escape = [0.0, 0.0]
            if now < self.nav_ready:
                return MagnetStep()  # still pushing after a jump: wait for the repeat
            self.captured, self.nav_ready = destination, now + NAV_REPEAT
            return MagnetStep(warp=(round(destination.x), round(destination.y)),
                              event="captured")
        if captured.kind == "hline":
            glide, effort = (dx, 0.0), (0.0, dy)
        elif captured.kind == "vline":
            glide, effort = (0.0, dy), (dx, 0.0)
        else:
            glide, effort = (0.0, 0.0), (dx, dy)
        self.escape[0] += effort[0]
        self.escape[1] += effort[1]
        if math.hypot(*self.escape) <= threshold:
            return MagnetStep(glide)
        exit_point = self._exit_point(captured, cursor, glide, snap_radius)
        self.ignored, self.captured, self.escape = captured, None, [0.0, 0.0]
        return MagnetStep(warp=exit_point, event="released")

    def _exit_point(self, captured: Target, cursor, glide, snap_radius: float) -> tuple[int, int]:
        """Just outside the capture zone, in the direction of the escape effort."""
        clearance = snap_radius + SAME_TARGET + 1  # also past the no-recapture zone
        ex, ey = self.escape
        if captured.kind == "hline":
            return (round(cursor[0] + glide[0]), round(captured.y + math.copysign(clearance, ey)))
        if captured.kind == "vline":
            return (round(captured.x + math.copysign(clearance, ex)), round(cursor[1] + glide[1]))
        norm = math.hypot(ex, ey)
        return (round(captured.x + ex / norm * clearance), round(captured.y + ey / norm * clearance))

    def _approach(self, cursor, dx, dy, strength, snap_radius, found: list[Target],
                  time_scale: float) -> MagnetStep:
        ahead = [
            target for target in found
            if _distance_to(target, cursor) > 1
            and (target.x - cursor[0]) * dx + (target.y - cursor[1]) * dy > 0
            and not (self.ignored is not None and _same(self.ignored, target))
        ]
        snap = _snap_candidate(cursor, dx, dy, ahead, snap_radius) if ahead else None
        if snap is not None:
            self.captured, self.escape = snap, [0.0, 0.0]
            return MagnetStep(warp=(round(snap.x), round(snap.y)), event="captured")
        return MagnetStep(pull_delta(dx, dy, cursor, ahead, strength, time_scale))
