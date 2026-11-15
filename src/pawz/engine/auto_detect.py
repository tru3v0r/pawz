"""Guess which drawn element is which input, from geometry alone.

The rules live in ``data/controllers/auto-detect.json`` (or the user's copy); this
module only implements the rule types they use. Pure Python: shapes come in as
plain rectangles, results go out as ``{element id: (input, confidence %)}``.
"""
from __future__ import annotations

import itertools
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

ROUND_KINDS = {"circle", "ellipse"}


@dataclass(frozen=True)
class Shape:
    id: str
    kind: str  # SVG tag: circle, ellipse, rect, path...
    x: float  # centre, 0..1 of the body width
    y: float  # centre, 0..1 of the body height
    size: float  # largest side, as a fraction of the body width
    width: float  # fractions of the body width
    height: float
    aspect: float  # body height / body width, to measure distances isotropically

    @property
    def round(self) -> bool:
        return self.kind in ROUND_KINDS

    def distance(self, x: float, y: float) -> float:
        return math.hypot(self.x - x, (self.y - y) * self.aspect)


def load_rules(*paths: Path) -> dict:
    """The first existing rules file (the user's copy, then the bundled one)."""
    for path in paths:
        if path and path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    raise FileNotFoundError("No auto-detect rules file")


def shapes_from_bounds(elements: list[tuple], rules: dict) -> list[Shape]:
    """``(id, kind, x, y, width, height[, label])`` in drawing units -> shapes relative to
    the box around them all.

    The reference frame is the box around every shape (the body, or both Joy-Con);
    elements larger than ``body.max_size`` of it (the body, outlines, rails) or smaller
    than ``body.min_size`` (specks) are left out.
    """
    solid = [element for element in elements if element[1] != "g"]
    if not solid:
        return []
    bx = min(element[2] for element in solid)
    by = min(element[3] for element in solid)
    bw = max(element[2] + element[4] for element in solid) - bx
    bh = max(element[3] + element[5] for element in solid) - by
    limits = rules.get("body", {})
    shapes = []
    for element_id, kind, x, y, width, height, *_ in solid:
        size = max(width, height) / bw
        if not limits.get("min_size", 0) <= size <= limits.get("max_size", 0.6):
            continue
        shapes.append(Shape(element_id, kind, (x + width / 2 - bx) / bw, (y + height / 2 - by) / bh,
                            size, width / bw, height / bw, bh / bw))
    return shapes


def _fit(error: float, tolerance: float) -> float:
    """1 for a perfect fit, 0 at the tolerance or beyond."""
    return max(0.0, 1.0 - error / tolerance) if tolerance > 0 else float(error == 0)


def _in_region(shape: Shape, region: dict) -> bool:
    return (region.get("x_min", -1) <= shape.x <= region.get("x_max", 2)
            and region.get("y_min", -1) <= shape.y <= region.get("y_max", 2))


def _shape_ok(shape: Shape, wanted: str | None) -> float:
    """How well a shape matches ``round`` / ``not-round`` / ``any`` (0..1)."""
    if wanted == "round":
        square = abs(shape.width - shape.height) / max(shape.width, shape.height)
        return 1.0 if shape.round else (0.6 if square < 0.1 else 0.0)
    if wanted == "not-round":
        return 0.0 if shape.round else 1.0
    return 1.0


class Detector:
    def __init__(self, rules: dict, family: str | None = None, labels: dict[str, str] | None = None):
        self.rules = rules
        self.family = family  # controller family: decides what a printed letter means
        self.labels = labels or {}  # element id -> Inkscape layer name
        self.found: dict[str, tuple[str, float]] = {}  # element id -> (input, score 0..1)
        self.groups: dict[str, tuple[float, float]] = {}  # rule id -> centre found
        self.face_size: float | None = None

    def run(self, shapes: list[Shape]) -> dict[str, tuple[str, int]]:
        only: set[str] | None = None  # set once a rule's stop_if_named is reached
        for rule in self.rules.get("rules", []):
            if only is not None and rule["id"] not in only:
                continue
            handler = getattr(self, "_" + rule["type"], None)
            if handler is not None:
                handler(rule, [shape for shape in shapes if shape.id not in self.found])
            # A drawing whose layers named most inputs needs no geometric guesses,
            # which would only add wrong ones (a touchpad on a pad that has none).
            if "stop_if_named" in rule and len(self.found) >= rule["stop_if_named"]:
                only = set(rule.get("still_run", []))
        minimum = self.rules.get("min_confidence", 0)
        results = {element: (name, round(score * 100)) for element, (name, score) in self.found.items()}
        return {element: result for element, result in results.items() if result[1] >= minimum}

    def _taken(self, name: str) -> bool:
        return any(found == name for found, _ in self.found.values())

    def _centre_of(self, reference: str, shapes_by_id: dict | None = None) -> tuple[float, float] | None:
        if reference in self.groups:
            return self.groups[reference]
        return next((self._positions[element] for element, (name, _) in self.found.items()
                     if name == reference), None)

    def _face_range(self, rule: dict) -> tuple[float, float]:
        low, high = rule.get("face_ratio", [0, 99])
        face = self.face_size or 0.08
        return low * face, high * face

    # -- rule types -----------------------------------------------------------------

    def _labels(self, rule: dict, shapes: list[Shape]):
        """Layers the artist named: "ZR Trigger", "L Bumper", "X Button"...

        Printed face-button letters depend on the family (X is the top button on a
        Nintendo controller, the left one on an Xbox one); without a family they are
        left to the geometric rules.
        """
        family = self.family or ""
        # Family patterns first: they decide words that differ between brands
        # ("Share" is Back on a PlayStation pad, the capture button on an Xbox).
        entries = list(rule.get("family_patterns", {}).get(family, {}).items())
        entries += list(rule.get("patterns", {}).items())
        face_pattern = rule.get("face_pattern", "^{letter}( button)?$")
        entries += [(name, face_pattern.format(letter=re.escape(letter)))
                    for letter, name in rule.get("face_letters", {}).get(family, {}).items()]
        compiled = [(name, re.compile(pattern, re.IGNORECASE)) for name, pattern in entries]
        for element_id, label in self.labels.items():
            for name, pattern in compiled:
                if pattern.search(label.strip()):
                    if not self._taken(name):
                        self.found[element_id] = (name, rule.get("confidence", 1))
                    break

    def _top_pairs(self, rule: dict, shapes: list[Shape]):
        """Wide shapes mirrored around the centre at the top of the drawing, topmost first:
        the triggers sit behind (higher), the bumpers in front. A single pair is taken
        for the bumpers, the ones a front view always shows."""
        region = rule.get("region", {})
        pool = [shape for shape in shapes if _in_region(shape, region)
                and shape.width >= rule.get("min_aspect", 1.5) * shape.height]
        tolerance = rule.get("tolerance", 0.06)
        pairs = []
        for a, b in itertools.combinations(pool, 2):
            left, right = sorted((a, b), key=lambda shape: shape.x)
            error = math.hypot(left.x + right.x - 1, (left.y - right.y) * left.aspect)
            size_error = abs(left.size - right.size) / max(left.size, right.size)
            if right.x - left.x > 0.2 and error < tolerance and size_error < 0.25:
                pairs.append(((left.y + right.y) / 2, left, right, _fit(error, tolerance) * (1 - size_error)))
        chosen, used = [], set()
        for _, left, right, score in sorted(pairs, key=lambda pair: pair[0]):  # topmost first
            if left.id not in used and right.id not in used:
                chosen.append((left, right, score))
                used |= {left.id, right.id}
        names = rule["pairs"]
        if len(chosen) == 1:  # one pair: bumpers, with less certainty
            names = names[-1:]
            chosen = [(left, right, score * 0.7) for left, right, score in chosen]
        for (left, right, score), pair_names in zip(chosen, names):
            for shape, name in zip((left, right), pair_names):
                self._assign(shape, name, score * rule.get("confidence", 1))

    def _diamond(self, rule: dict, shapes: list[Shape]):
        """Four shapes: one left, one right, one top, one bottom around a common centre."""
        pool = [shape for shape in shapes if _in_region(shape, rule.get("region", {}))
                and shape.size <= rule.get("max_size", 1) and _shape_ok(shape, rule.get("shape")) > 0]
        best, best_score = None, 0.0
        for four in itertools.combinations(pool, 4):
            by_x = sorted(four, key=lambda shape: shape.x)
            left, right = by_x[0], by_x[-1]
            top, bottom = sorted(by_x[1:3], key=lambda shape: shape.y)
            horizontal = right.x - left.x
            vertical = (bottom.y - top.y) * left.aspect
            if horizontal <= 0 or vertical <= 0:
                continue
            spacing = (horizontal + vertical) / 2
            errors = [
                abs(left.y - right.y) * left.aspect / spacing,  # left and right level
                abs(top.x - bottom.x) / spacing,  # top and bottom aligned
                math.hypot((left.x + right.x - top.x - bottom.x) / 2,
                           (left.y + right.y - top.y - bottom.y) / 2 * left.aspect) / spacing,  # one centre
                abs(horizontal - vertical) / spacing,  # as wide as tall
            ]
            sizes = [shape.size for shape in four]
            size_error = (max(sizes) - min(sizes)) / max(sizes)
            score = (sum(_fit(error, rule.get("alignment_tolerance", 0.25)) for error in errors) / len(errors)
                     * _fit(size_error, rule.get("size_tolerance", 0.15))
                     * min(_shape_ok(shape, rule.get("shape")) for shape in four))
            centre = ((left.x + right.x) / 2, (top.y + bottom.y) / 2)
            if rule.get("mirror_of"):
                other = self.groups.get(rule["mirror_of"])
                if other is None:
                    continue
                # Mirrored left-right; the vertical tolerance is separate (on Joy-Con the
                # d-pad sits lower than the face buttons).
                x_tolerance = rule.get("mirror_tolerance", 0.08)
                y_tolerance = rule.get("mirror_y_tolerance", x_tolerance)
                mirror_error = math.hypot((centre[0] - (1 - other[0])) / x_tolerance,
                                          (centre[1] - other[1]) * left.aspect / y_tolerance)
                score *= _fit(mirror_error, 1.0) ** 0.5
            if score > best_score:
                best, best_score = (left, right, top, bottom, centre), score
        if best is None or best_score <= 0:
            return
        left, right, top, bottom, centre = best
        names = rule["inputs"]
        for shape, slot in ((left, "left"), (right, "right"), (top, "top"), (bottom, "bottom")):
            self._assign(shape, names[slot], best_score * rule.get("confidence", 1))
        self.groups[rule["id"]] = centre
        if self.face_size is None:
            self.face_size = sum(shape.size for shape in (left, right, top, bottom)) / 4

    def _sticks(self, rule: dict, shapes: list[Shape]):
        low, high = self._face_range(rule)
        pool = [shape for shape in shapes if low <= shape.size <= high and _shape_ok(shape, rule.get("shape")) > 0]
        face = self.groups.get("face-buttons")
        rights = [shape for shape in pool if shape.x > 0.5]
        right = min(rights, key=lambda shape: shape.distance(*face) if face else -shape.size, default=None)
        lefts = [shape for shape in pool if shape.x < 0.5]
        if right is not None:
            self._assign(right, rule["inputs"]["right"],
                         _shape_ok(right, rule.get("shape")) * (1.0 if face else 0.7) * rule.get("confidence", 1))
            # Same size as the right stick; mirror symmetry is a bonus, not a requirement
            # (Xbox and Switch Pro sticks are offset).
            def left_score(shape):
                size = _fit(abs(shape.size - right.size) / right.size, rule.get("size_tolerance", 0.12))
                mirror = _fit(math.hypot(shape.x - (1 - right.x), (shape.y - right.y) * shape.aspect),
                              rule.get("mirror_tolerance", 0.06))
                return size * (0.8 + 0.2 * mirror) * _shape_ok(shape, rule.get("shape"))
            left = max(lefts, key=left_score, default=None)
            if left is not None and left_score(left) > 0:
                self._assign(left, rule["inputs"]["left"], left_score(left) * rule.get("confidence", 1))
        elif lefts and face:  # face buttons but a single stick, on the left (Steam Controller)
            left = max(lefts, key=lambda shape: shape.size)
            self._assign(left, rule["inputs"]["left"], 0.6 * rule.get("confidence", 1))

    def _mirror(self, rule: dict, shapes: list[Shape]):
        """One shape where a reference (input or group) would be, mirrored left-right."""
        if self._taken(rule["input"]):
            return
        low, high = self._face_range(rule)
        pool = [shape for shape in shapes if _in_region(shape, rule.get("region", {})) and low <= shape.size <= high]
        references = rule["mirror_of"] if isinstance(rule["mirror_of"], list) else [rule["mirror_of"]]
        best, best_score = None, 0.0
        for reference in references:
            centre = self._centre_of(reference)
            if centre is None:
                continue
            for shape in pool:
                score = _fit(shape.distance(1 - centre[0], centre[1]), rule.get("tolerance", 0.1))
                score *= 1.0 if _shape_ok(shape, rule.get("prefer_shape")) else 0.75
                if score > best_score:
                    best, best_score = shape, score
        if best is not None and best_score > 0:
            self._assign(best, rule["input"], best_score * rule.get("confidence", 1))

    def _centre_pairs(self, rule: dict, shapes: list[Shape]):
        low, high = self._face_range(rule)
        pool = [shape for shape in shapes if _in_region(shape, rule.get("region", {})) and low <= shape.size <= high
                and _shape_ok(shape, rule.get("shape")) > 0]
        tolerance = rule.get("tolerance", 0.04)
        pairs = []
        for a, b in itertools.combinations(pool, 2):
            left, right = sorted((a, b), key=lambda shape: shape.x)
            error = math.hypot(left.x + right.x - 1, (left.y - right.y) * left.aspect)
            if right.x - left.x > 0.04 and error < tolerance:
                pairs.append((right.x - left.x, left, right, _fit(error, tolerance)))
        used: set[str] = set()
        names = iter(rule["pairs"])
        for _, left, right, score in sorted(pairs, key=lambda pair: -pair[0]):  # widest first
            if left.id in used or right.id in used:
                continue
            pair_names = next(names, None)
            if pair_names is None:
                break
            for shape, name in zip((left, right), pair_names):
                if not self._taken(name):
                    self._assign(shape, name, score * rule.get("confidence", 1))
            used |= {left.id, right.id}

    def _centre_single(self, rule: dict, shapes: list[Shape]):
        if self._taken(rule["input"]):
            return
        low, high = self._face_range(rule)
        pool = [shape for shape in shapes if _in_region(shape, rule.get("region", {}))
                and _shape_ok(shape, rule.get("shape")) > 0
                and shape.width <= rule.get("max_aspect", 99) * shape.height
                and (("min_width" in rule and rule["min_width"] <= shape.width <= rule.get("max_width", 1))
                     or ("min_width" not in rule and low <= shape.size <= high))]
        tolerance = rule.get("tolerance", 0.03)
        best = min(pool, key=lambda shape: abs(shape.x - 0.5), default=None)
        if best is not None and abs(best.x - 0.5) < tolerance:
            self._assign(best, rule["input"], _fit(abs(best.x - 0.5), tolerance * 2) * rule.get("confidence", 1))

    def _assign(self, shape: Shape, name: str, score: float):
        if score > 0 and not self._taken(name):
            self.found[shape.id] = (name, score)
            self._positions[shape.id] = (shape.x, shape.y)

    @property
    def _positions(self) -> dict[str, tuple[float, float]]:
        if not hasattr(self, "_positions_store"):
            self._positions_store: dict[str, tuple[float, float]] = {}
        return self._positions_store


def detect(elements: list[tuple], rules: dict, family: str | None = None) -> dict[str, tuple[str, int]]:
    """``{element id: (input, confidence %)}`` for the elements the rules recognise.

    ``elements`` are ``(id, kind, x, y, width, height[, label])``; ``family`` is the
    controller family (``nintendo``, ``xbox``, ``playstation``...), used by label rules.
    """
    labels = {element[0]: element[6] for element in elements if len(element) > 6 and element[6]}
    return Detector(rules, family, labels).run(shapes_from_bounds(elements, rules))
