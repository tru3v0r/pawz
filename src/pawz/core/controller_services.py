"""Device identity, model resolution and raw-input calibration, independent of Qt."""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from pawz.core.controller_catalog import ControllerDefinition
from pawz.core.controller_inputs import LogicalAxis, LogicalButton

GENERIC_MODEL = "generic.sdl-gamecontroller"


def resolve_model(definitions: tuple[ControllerDefinition, ...], guid: str,
                  name: str, override: str | None = None) -> str:
    by_id = {model.id: model for model in definitions}
    if override in by_id:
        return override
    matches = [model for model in definitions if guid and guid.lower() in
               {value.lower() for value in model.known_guids}]
    if len(matches) == 1:
        return matches[0].id
    # Names are hints only; do not claim hardware verification from them.
    matches = [model for model in definitions if model.model.casefold() == name.casefold()]
    return matches[0].id if len(matches) == 1 else GENERIC_MODEL


@dataclass
class DeviceIdentityRegistry:
    """Retain identities by SDL instance while connected, never by GUID alone.

    SDL exposes no universally persistent physical identity. Reconnect matching of
    indistinguishable devices is best effort, restricted to unoccupied saved slots.
    """

    instances: dict[int, str] = field(default_factory=dict)

    def acquire(self, instance: int, guid: str, known: dict[str, str],
                preferences: dict[str, dict], occupied: set[str]) -> str:
        if instance in self.instances:
            return self.instances[instance]
        candidates = [key for key in known if key not in occupied and
                      (preferences.get(key, {}).get("guid") == guid or key.startswith(guid + "#"))]
        key = candidates[0] if candidates else "device-" + str(uuid4())
        self.instances[instance] = key
        return key

    def retain(self, instances: set[int]) -> None:
        self.instances = {instance: key for instance, key in self.instances.items()
                          if instance in instances}


def validate_mapping(mapping: dict[str, str]) -> dict[str, str]:
    """Bindings use SDL raw syntax bN, aN, +/-aN or hN.M."""
    import re
    if not isinstance(mapping, dict):
        raise ValueError("A hardware mapping must be a dictionary")
    inputs = {value.value for value in LogicalButton} | {value.value for value in LogicalAxis}
    result = {}
    for logical, source in mapping.items():
        if logical not in inputs or not isinstance(source, str) or not re.fullmatch(
                r"(?:b\d+|[+-]?a\d+|h\d+\.(?:1|2|4|8))", source):
            raise ValueError(f"Invalid mapping: {logical}={source}")
        result[logical] = source
    return result


def read_raw(joystick, source: str) -> float:
    if source.startswith("b"):
        return float(joystick.get_button(int(source[1:])))
    if source.startswith("h"):
        index, mask = map(int, source[1:].split("."))
        x, y = joystick.get_hat(index)
        return float({1: y > 0, 2: x > 0, 4: y < 0, 8: x < 0}[mask])
    polarity = source[0] if source[0] in "+-" else ""
    value = float(joystick.get_axis(int(source[len(polarity) + 1:])))
    return max(0.0, value if polarity == "+" else -value) if polarity else value


class Calibration:
    """Capture changed buttons, hats and axes from an actual joystick snapshot."""

    def __init__(self, joystick):
        self.joystick = joystick
        self.baseline = self.snapshot()
        self.mapping: dict[str, str] = {}

    def snapshot(self) -> dict[str, float]:
        joy = self.joystick
        sources = ([f"b{i}" for i in range(joy.get_numbuttons())] +
                   [f"a{i}" for i in range(joy.get_numaxes())] +
                   [f"h{i}.{mask}" for i in range(joy.get_numhats()) for mask in (1, 2, 4, 8)])
        return {source: read_raw(joy, source) for source in sources}

    def capture(self, logical: str) -> str | None:
        current = self.snapshot()
        changes = [(abs(value - self.baseline[source]), source, value)
                   for source, value in current.items()]
        if not changes:
            return None
        delta, source, value = max(changes)
        if delta < 0.65:
            return None
        if source.startswith("a") and logical in LogicalButton._value2member_map_:
            source = ("+" if value > 0 else "-") + source
        self.mapping.update(validate_mapping({logical: source}))
        return source
