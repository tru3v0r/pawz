"""Catalogue of bindable actions, and the output they drive.

Every action is declared once here: its identifier (stored in profiles), its label
(shown in the settings, translated with ``pawz.i18n.tr``), and what it does. Settings validation, the profile editor,
the gesture engine and execution all read this table, so adding an action is a
single entry.

Execution goes through an ``OutputSink``: the Windows implementation lives in
``pawz.infra``, tests and other front-ends can pass their own.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


def QT_TR_NOOP(text: str) -> str:  # marks labels for pyside6-lupdate
    return text


@dataclass(frozen=True)
class Action:
    id: str
    label: str
    mouse: str | None = None  # mouse button, held as long as the controller button
    keys: str = ""  # fixed key combination
    custom_keys: bool = False  # the key combination comes from the binding
    internal: bool = False  # handled by pawz itself (not sent to Windows)


CATALOGUE: tuple[Action, ...] = (
    Action("none", QT_TR_NOOP("No action")),
    Action("left_click", QT_TR_NOOP("Left click"), mouse="left"),
    Action("right_click", QT_TR_NOOP("Right click"), mouse="right"),
    Action("middle_click", QT_TR_NOOP("Middle click"), mouse="middle"),
    Action("win", QT_TR_NOOP("Start menu"), keys="win"),
    Action("volume_up", QT_TR_NOOP("Volume up"), keys="volume_up"),
    Action("volume_down", QT_TR_NOOP("Volume down"), keys="volume_down"),
    Action("previous", QT_TR_NOOP("Previous page"), keys="browser_back"),
    Action("next", QT_TR_NOOP("Next page"), keys="browser_forward"),
    Action("tab_previous", QT_TR_NOOP("Previous tab"), keys="ctrl+shift+tab"),
    Action("tab_next", QT_TR_NOOP("Next tab"), keys="ctrl+tab"),
    # Site/app-specific hotkeys (YouTube, VLC), not system media keys.
    Action("play_pause", QT_TR_NOOP("Play / pause"), keys="space"),
    Action("fullscreen", QT_TR_NOOP("Full screen"), keys="f"),
    Action("subtitles", QT_TR_NOOP("Subtitles"), keys="c"),
    Action("key_combo", QT_TR_NOOP("Keyboard shortcut"), custom_keys=True),
    Action("open_settings", QT_TR_NOOP("Open settings"), internal=True),
    Action("game_mode", QT_TR_NOOP("Toggle game mode"), internal=True),
)
BY_ID = {action.id: action for action in CATALOGUE}
ACTION_IDS = tuple(BY_ID)
LABELS = {action.id: action.label for action in CATALOGUE}


def get(action_id: str) -> Action:
    try:
        return BY_ID[action_id]
    except KeyError:
        raise ValueError(f"Unknown action: {action_id}") from None


def mouse_button(action_id: str) -> str | None:
    """Mouse button an action holds, if it is a click."""
    action = BY_ID.get(action_id)
    return action.mouse if action else None


class OutputSink(Protocol):
    """Everything pawz sends to the system."""

    def mouse_down(self, button: str) -> None: ...
    def mouse_up(self, button: str) -> None: ...
    def click(self, button: str) -> None: ...
    def key_combo(self, keys: str) -> None: ...
    def move(self, dx: float, dy: float, magnet_strength: float, dt: float,
             full_speed: float, background: bool) -> str | None: ...
    def scroll(self, steps: int) -> None: ...


def execute(action_id: str, keys: str, output: OutputSink) -> None:
    """Perform an action on ``output``. Internal actions are left to the caller."""
    action = get(action_id)
    if action.mouse:
        output.click(action.mouse)
    elif action.custom_keys:
        output.key_combo(keys)
    elif action.keys:
        output.key_combo(action.keys)
