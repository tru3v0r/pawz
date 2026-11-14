"""Device identity, model resolution and raw-input calibration, independent of Qt."""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from pawz.core.controller_catalog import ControllerDefinition
from pawz.core.controller_inputs import LogicalAxis, LogicalButton

GENERIC_MODEL = "generic.sdl-gamecontroller"


# USB vendor:product ids (as in SDL's usb_ids.h) of the built-in models.
MODEL_USB_IDS = {
    "microsoft.xbox-360": ("045e:028e", "045e:02a1", "045e:0719"),
    "microsoft.xbox-one": ("045e:02d1", "045e:02dd"),
    "microsoft.xbox-one-s": ("045e:02ea", "045e:02e0", "045e:02fd", "045e:0b20"),
    "microsoft.xbox-series": ("045e:0b12", "045e:0b13"),
    "microsoft.elite-1": ("045e:02e3",),
    "microsoft.elite-2": ("045e:0b00", "045e:0b05", "045e:0b22"),
    "microsoft.adaptive": ("045e:0b0a", "045e:0b0c", "045e:0b21"),
    "sony.dualshock-3": ("054c:0268",),
    "sony.dualshock-4": ("054c:05c4", "054c:09cc", "054c:0ba0"),
    "sony.dualsense": ("054c:0ce6",),
    "sony.dualsense-edge": ("054c:0df2",),
    "nintendo.switch-pro": ("057e:2009",),
    "nintendo.joycon": ("057e:2006", "057e:2007", "057e:200e"),
    "logitech.f310": ("046d:c216", "046d:c21d"),
    "logitech.f510": ("046d:c218", "046d:c21e"),
    "logitech.f710": ("046d:c219", "046d:c21f"),
    "valve.steam-controller": ("28de:1102", "28de:1106", "28de:1142"),
    "valve.steam-deck": ("28de:1205",),
}
# Fragments of SDL device names, most specific first.
NAME_HINTS = (
    ("elite series 2", "microsoft.elite-2"), ("elite", "microsoft.elite-1"),
    ("adaptive", "microsoft.adaptive"), ("xbox series", "microsoft.xbox-series"),
    ("xbox one s", "microsoft.xbox-one-s"), ("xbox one", "microsoft.xbox-one"),
    ("xbox 360", "microsoft.xbox-360"), ("xbox", "microsoft.xbox-one"),
    ("dualsense edge", "sony.dualsense-edge"), ("dualsense", "sony.dualsense"),
    ("ps5", "sony.dualsense"), ("dualshock 4", "sony.dualshock-4"), ("ps4", "sony.dualshock-4"),
    ("dualshock 3", "sony.dualshock-3"), ("ps3", "sony.dualshock-3"),
    ("pro controller", "nintendo.switch-pro"), ("joy-con", "nintendo.joycon"),
    ("steam deck", "valve.steam-deck"), ("steam controller", "valve.steam-controller"),
    ("f310", "logitech.f310"), ("f510", "logitech.f510"), ("f710", "logitech.f710"),
)


def usb_id(guid: str) -> str | None:
    """``"vvvv:pppp"`` from an SDL2 joystick GUID, when it carries USB ids.

    Layout (little-endian 16-bit words): bus, CRC, vendor, 0, product, 0, version, ...
    XInput-only devices on Windows have no ids ("xinput" in the GUID instead).
    """
    try:
        raw = bytes.fromhex(guid)
    except ValueError:
        return None
    if len(raw) != 16 or raw[6:8] != bytes(2) or raw[10:12] != bytes(2):
        return None
    vendor, product = int.from_bytes(raw[4:6], "little"), int.from_bytes(raw[8:10], "little")
    return f"{vendor:04x}:{product:04x}" if vendor and product else None


def resolve_model(definitions: tuple[ControllerDefinition, ...], guid: str,
                  name: str, override: str | None = None) -> str:
    """The catalog model to show for a device: the user's choice, then a known GUID,
    then the USB ids in the GUID, then the exact model name, then name fragments."""
    by_id = {model.id: model for model in definitions}
    if override in by_id:
        return override
    matches = [model for model in definitions if guid and guid.lower() in
               {value.lower() for value in model.known_guids}]
    if len(matches) == 1:
        return matches[0].id
    device_ids = usb_id(guid or "")
    for model_id, ids in MODEL_USB_IDS.items():
        if device_ids in ids and model_id in by_id:
            return model_id
    # Names are hints only; do not claim hardware verification from them.
    matches = [model for model in definitions if model.model.casefold() == name.casefold()]
    if len(matches) == 1:
        return matches[0].id
    folded = name.casefold()
    for fragment, model_id in NAME_HINTS:
        if fragment in folded and model_id in by_id:
            return model_id
    return GENERIC_MODEL


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
