from unittest.mock import Mock, call

import pytest

from pawz.core.models import BROWSER_PROCESSES, Settings
from pawz.core.pointer import SubpixelAccumulator, radial_deadzone
from pawz.infra import windows
from pawz.infra.browser import BrowserBridge


def test_radial_deadzone_keeps_small_off_axis_component():
    x, y = radial_deadzone(0.6, 0.1, 0.18)
    assert x > 0 and y > 0
    assert radial_deadzone(0.1, 0.1, 0.18) == (0.0, 0.0)
    assert radial_deadzone(1.0, 0.0, 0.18) == pytest.approx((1.0, 0.0))


def test_subpixel_accumulator_emits_slow_movement_over_time():
    accumulator = SubpixelAccumulator()
    steps = [accumulator.take(0.4, -0.4) for _ in range(5)]
    assert sum(step[0] for step in steps) == 2
    assert sum(step[1] for step in steps) == -2


def test_slow_pointer_movement_is_not_lost(monkeypatch):
    mouse_event = Mock()
    monkeypatch.setattr(windows, "send_mouse", mouse_event)
    monkeypatch.setattr(windows, "_pointer_residual", SubpixelAccumulator())
    for _ in range(4):
        windows.move(0.5, 0)
    assert mouse_event.call_args_list == [call(0x0001, 1, 0), call(0x0001, 1, 0)]


@pytest.mark.parametrize(("action", "key"), [("previous", 0xA6), ("next", 0xA7)])
def test_page_navigation_uses_browser_keys(monkeypatch, action, key):
    send_keys = Mock()
    monkeypatch.setattr(windows, "send_keys", send_keys)
    windows.perform(action)
    send_keys.assert_called_once_with([(key, 0), (key, 2)])


def test_arrow_keys_are_sent_as_extended_keys(monkeypatch):
    send_keys = Mock()
    monkeypatch.setattr(windows, "send_keys", send_keys)
    windows.key_combo("ctrl+left")
    send_keys.assert_called_once_with([(0x11, 0), (0x25, 1), (0x25, 3), (0x11, 2)])


def test_function_keys_and_unknown_keys():
    assert windows.key_code("f5") == 0x74
    with pytest.raises(ValueError, match="Unknown key"):
        windows.key_code("é")


def test_unknown_action_is_reported():
    with pytest.raises(ValueError, match="Unknown action"):
        windows.perform("teleport")


def test_bridge_domain_does_not_expire_and_can_be_cleared():
    bridge = BrowserBridge("token", 0)
    bridge._url_by_process["chrome.exe"] = "https://www.youtube.com/watch?v=1"
    assert bridge.domain("chrome.exe") == "www.youtube.com"
    bridge._url_by_process["chrome.exe"] = ""
    assert bridge.domain("chrome.exe") == ""


def test_default_profile_covers_every_supported_browser():
    profile = Settings.defaults().profiles["Default"]
    for browser in BROWSER_PROCESSES:
        assert profile.resolve("RIGHT_SHOULDER", browser).action == "tab_next"
