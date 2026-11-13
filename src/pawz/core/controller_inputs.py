"""Logical controller inputs and the pygame/SDL2 compatibility boundary."""
from __future__ import annotations

from enum import StrEnum


class LogicalButton(StrEnum):
    SOUTH = "SOUTH"
    EAST = "EAST"
    WEST = "WEST"
    NORTH = "NORTH"
    LEFT_SHOULDER = "LEFT_SHOULDER"
    RIGHT_SHOULDER = "RIGHT_SHOULDER"
    LEFT_STICK = "LEFT_STICK"
    RIGHT_STICK = "RIGHT_STICK"
    DPAD_UP = "DPAD_UP"
    DPAD_DOWN = "DPAD_DOWN"
    DPAD_LEFT = "DPAD_LEFT"
    DPAD_RIGHT = "DPAD_RIGHT"
    BACK = "BACK"
    START = "START"
    GUIDE = "GUIDE"
    MISC1 = "MISC1"
    PADDLE1 = "PADDLE1"
    PADDLE2 = "PADDLE2"
    PADDLE3 = "PADDLE3"
    PADDLE4 = "PADDLE4"
    TOUCHPAD = "TOUCHPAD"


class LogicalAxis(StrEnum):
    LEFT_X = "LEFT_X"
    LEFT_Y = "LEFT_Y"
    RIGHT_X = "RIGHT_X"
    RIGHT_Y = "RIGHT_Y"
    LEFT_TRIGGER = "LEFT_TRIGGER"
    RIGHT_TRIGGER = "RIGHT_TRIGGER"


# pygame 2.x uses SDL2 GameController button ordering; it does not expose SDL3's
# renamed button constants. Keep this adaptation explicit and testable.
SDL2_BUTTON_TO_LOGICAL: dict[int, LogicalButton] = {
    0: LogicalButton.SOUTH,
    1: LogicalButton.EAST,
    2: LogicalButton.WEST,
    3: LogicalButton.NORTH,
    4: LogicalButton.BACK,
    5: LogicalButton.GUIDE,
    6: LogicalButton.START,
    7: LogicalButton.LEFT_STICK,
    8: LogicalButton.RIGHT_STICK,
    9: LogicalButton.LEFT_SHOULDER,
    10: LogicalButton.RIGHT_SHOULDER,
    11: LogicalButton.DPAD_UP,
    12: LogicalButton.DPAD_DOWN,
    13: LogicalButton.DPAD_LEFT,
    14: LogicalButton.DPAD_RIGHT,
    15: LogicalButton.MISC1,
    16: LogicalButton.PADDLE1,
    17: LogicalButton.PADDLE2,
    18: LogicalButton.PADDLE3,
    19: LogicalButton.PADDLE4,
    20: LogicalButton.TOUCHPAD,
}

SDL2_AXIS_TO_LOGICAL: dict[int, LogicalAxis] = {
    0: LogicalAxis.LEFT_X,
    1: LogicalAxis.LEFT_Y,
    2: LogicalAxis.RIGHT_X,
    3: LogicalAxis.RIGHT_Y,
    4: LogicalAxis.LEFT_TRIGGER,
    5: LogicalAxis.RIGHT_TRIGGER,
}

LEGACY_BUTTON_ALIASES: dict[str, LogicalButton] = {
    "a": LogicalButton.SOUTH,
    "b": LogicalButton.EAST,
    "x": LogicalButton.WEST,
    "y": LogicalButton.NORTH,
    "minus": LogicalButton.BACK,
    "home": LogicalButton.GUIDE,
    "plus": LogicalButton.START,
    "left_stick": LogicalButton.LEFT_STICK,
    "right_stick": LogicalButton.RIGHT_STICK,
    "l": LogicalButton.LEFT_SHOULDER,
    "r": LogicalButton.RIGHT_SHOULDER,
    "dpad_up": LogicalButton.DPAD_UP,
    "dpad_down": LogicalButton.DPAD_DOWN,
    "dpad_left": LogicalButton.DPAD_LEFT,
    "dpad_right": LogicalButton.DPAD_RIGHT,
}


def logical_button_for_sdl2(button_index: int) -> str | None:
    """Translate a standardized SDL2 GameController button index."""
    button = SDL2_BUTTON_TO_LOGICAL.get(button_index)
    return button.value if button is not None else None


def migrate_legacy_trigger(trigger: str) -> str:
    """Translate stored pre-logical button names, preserving chord order."""
    parts = trigger.split("+")
    translated: list[str] = []
    for part in parts:
        normalized = part.strip().lower()
        translated.append(LEGACY_BUTTON_ALIASES.get(
            normalized, LogicalButton(normalized.upper()).value
            if normalized.upper() in LogicalButton._value2member_map_
            else part))
    return "+".join(translated)
