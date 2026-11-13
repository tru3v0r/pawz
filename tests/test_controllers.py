from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
from PySide6.QtCore import QObject

from pawz.core.controllers import BUTTON_MAP, ControllerManager, battery_percentage
from pawz.core.models import Binding, Profile, Settings
from pawz.engine.gestures import GestureEngine


@pytest.mark.parametrize(
    ("level", "percentage"),
    [
        ("empty", 0),
        ("LOW", 20),
        ("medium", 60),
        ("full", 100),
        ("max", 100),
        ("wired", None),
        ("unknown", None),
    ],
)
def test_battery_percentage(level, percentage):
    assert battery_percentage(level) == percentage


def test_console_dpad_buttons_map_to_default_keyboard_arrows():
    settings = Settings.defaults()
    profile = settings.profiles["Default"]

    assert {index: BUTTON_MAP[index] for index in range(11, 15)} == {
        11: "DPAD_UP",
        12: "DPAD_DOWN",
        13: "DPAD_LEFT",
        14: "DPAD_RIGHT",
    }
    assert [profile.resolve(BUTTON_MAP[index]).keys for index in range(11, 15)] == [
        "up", "down", "left", "right"
    ]


def test_unassigned_controller_uses_configured_default_profile():
    manager = ControllerManager.__new__(ControllerManager)
    manager.settings = Settings.defaults()
    manager.config = manager.settings  # input thread reads its own copy
    manager.settings.profiles["Alternate"] = Profile("Alternate")
    manager.settings.default_profile = "Alternate"

    assert manager._profile("controller#0").name == "Alternate"


def test_left_click_is_held_until_controller_button_release(monkeypatch):
    manager = ControllerManager.__new__(ControllerManager)
    QObject.__init__(manager)
    manager.settings = Settings.defaults()
    manager.config = manager.settings  # input thread reads its own copy
    manager.bridge = SimpleNamespace(domain=lambda _app: "")
    manager.gestures = GestureEngine()
    manager.output = Mock()
    monkeypatch.setattr("pawz.core.controllers.windows.active_process", lambda: "")

    manager._press_button("controller#0", "EAST", 1.0)
    manager.output.mouse_down.assert_called_once_with("left")
    manager.output.mouse_up.assert_not_called()

    manager._release_button("controller#0", "EAST")
    manager.output.mouse_up.assert_called_once_with("left")
    manager.output.click.assert_not_called()  # held, not clicked


def test_controller_combo_dispatches_once_and_suppresses_single_buttons(monkeypatch):
    manager = ControllerManager.__new__(ControllerManager)
    QObject.__init__(manager)
    manager.settings = Settings.defaults()
    manager.config = manager.settings  # input thread reads its own copy
    manager.settings.profiles["Default"].apps["brave.exe"] = {
        "SOUTH+LEFT_SHOULDER": Binding("tab_previous"),
        "LEFT_SHOULDER": Binding("previous"),
    }
    manager.bridge = SimpleNamespace(domain=lambda _app: "")
    manager.gestures = GestureEngine()
    manager.output = Mock()
    monkeypatch.setattr("pawz.core.controllers.windows.active_process", lambda: "brave.exe")

    manager._press_button("controller#0", "SOUTH", 1.0)
    manager._press_button("controller#0", "LEFT_SHOULDER", 1.1)

    assert manager.output.key_combo.call_args_list == [call("ctrl+shift+tab")]
    manager._release_button("controller#0", "SOUTH")
    manager._release_button("controller#0", "LEFT_SHOULDER")
    assert manager.output.key_combo.call_count == 1
    manager.output.click.assert_not_called()  # the chord swallowed SOUTH's right click
