"""Threading contract of ControllerManager: config isolation, hardware hand-off, shutdown."""
from types import SimpleNamespace

import pytest

from pawz.core import controllers
from pawz.core.controllers import ControllerManager
from pawz.core.models import Profile, Settings


@pytest.fixture
def fake_sdl(monkeypatch, tmp_path):
    """SDL with a mutable list of connected joysticks."""
    connected = []
    monkeypatch.setattr(controllers, "DATA_DIR", tmp_path)
    monkeypatch.setattr(controllers.pygame, "init", lambda: None)
    monkeypatch.setattr(controllers.pygame.joystick, "init", lambda: None)
    monkeypatch.setattr(controllers.pygame.event, "pump", lambda: None)
    monkeypatch.setattr(controllers.pygame.joystick, "get_count", lambda: len(connected))
    monkeypatch.setattr(controllers.pygame.joystick, "Joystick", lambda index: connected[index])
    monkeypatch.setattr(controllers.sdl_controller, "init", lambda: None)
    monkeypatch.setattr(controllers.sdl_controller, "is_controller", lambda _index: True)
    monkeypatch.setattr(controllers.sdl_controller, "Controller", lambda index: connected[index])
    monkeypatch.setattr(controllers.windows, "active_process", lambda: "")
    return connected


def joystick(instance, name="Pad"):
    return SimpleNamespace(
        init=lambda: None, get_guid=lambda: "a" * 32, get_instance_id=lambda: instance,
        get_name=lambda: name, get_power_level=lambda: "full",
        get_button=lambda _index: 0, get_axis=lambda _index: 0)


def bridge():
    return SimpleNamespace(domain=lambda _process: "")


def at_rest(manager):
    """Mark every stick as already seen centered, as after normal use."""
    manager._sticks_at_rest |= {(key, stick) for key in manager.controllers
                                for stick in ("LEFT", "RIGHT")}
    return manager


def test_input_side_reads_a_private_copy_until_sync(qapp, fake_sdl):
    settings = Settings.defaults()
    manager = ControllerManager(settings, bridge(), threaded=False)
    settings.profiles["Late"] = Profile("Late")
    assert "Late" not in manager.config.profiles
    manager.sync_settings()
    assert "Late" in manager.config.profiles
    assert manager.config is not settings
    manager.stop()


def test_discovered_devices_are_written_to_live_settings(qapp, fake_sdl):
    fake_sdl.append(joystick(7, "Arcade stick"))
    settings = Settings.defaults()
    changes = []
    manager = ControllerManager(settings, bridge(), threaded=False)
    manager.devices_changed.connect(lambda: changes.append(True))
    fake_sdl.append(joystick(8, "Second pad"))
    manager.poll()
    keys = list(manager.controllers)
    assert [settings.known_devices[key] for key in keys] == ["Arcade stick", "Second pad"]
    assert settings.device_preferences[keys[0]]["detected_name"] == "Arcade stick"
    assert settings.primary_device == keys[0]
    assert manager.config.primary_device == keys[0]  # pushed to the input side at once
    assert changes == [True]
    manager.stop()


def test_stop_releases_held_mouse_buttons(qapp, fake_sdl, monkeypatch):
    released = []
    monkeypatch.setattr(controllers.windows, "mouse_button_down", lambda _button: None)
    monkeypatch.setattr(controllers.windows, "mouse_button_up", released.append)
    fake_sdl.append(joystick(1))
    manager = ControllerManager(Settings.defaults(), bridge(), threaded=False)
    device = next(iter(manager.controllers))
    manager._press_button(device, "EAST", 0)  # default profile: EAST = left click
    manager.stop()
    assert released == ["left"]
    assert not manager.gestures.is_pressed(device, "EAST")


def test_threaded_manager_polls_off_the_qt_thread_and_stops(qapp, qtbot, fake_sdl):
    fake_sdl.append(joystick(3))
    manager = ControllerManager(Settings.defaults(), bridge())
    errors = []
    manager.error.connect(errors.append)
    with qtbot.waitSignal(manager.devices_changed, timeout=3000):
        manager.start()
    qtbot.waitUntil(lambda: manager.poll_rate > 0, timeout=3000)
    thread = manager._thread
    manager.stop()
    assert thread.isFinished()
    assert errors == []


def test_every_tick_moves_the_cursor_even_if_the_coarse_clock_stalls(qapp, fake_sdl, monkeypatch):
    # time.monotonic() advances in ~15.6 ms steps on Windows: at 250 Hz, 3 ticks out
    # of 4 used to see dt == 0 and send no movement, then one 4x jump.
    pad = joystick(1)
    pad.get_axis = lambda index: 0.8 * 32767 if index == 0 else 0
    fake_sdl.append(pad)
    clock = [100.0]
    monkeypatch.setattr(controllers.time, "perf_counter", lambda: clock[0])
    monkeypatch.setattr(controllers.time, "monotonic", lambda: 100.0)
    moves = []
    monkeypatch.setattr(controllers.windows, "move", lambda dx, dy, *_args: moves.append(dx))
    manager = at_rest(ControllerManager(Settings.defaults(), bridge(), threaded=False))
    for _ in range(8):
        clock[0] += 0.004
        manager.poll()
    assert len(moves) == 8
    assert min(moves) > 0
    assert max(moves) - min(moves) < 0.01  # steady, not stalled-then-burst
    manager.stop()


def test_magnet_events_rumble_the_controller_that_moved_the_cursor(qapp, fake_sdl, monkeypatch):
    from unittest.mock import Mock
    pad = joystick(1)
    pad.get_axis = lambda index: 0.8 * 32767 if index == 0 else 0
    pad.rumble = Mock()
    fake_sdl.append(pad)
    events = iter(["captured", None, "released"])
    monkeypatch.setattr(controllers.windows, "move", lambda *_args: next(events))
    manager = at_rest(ControllerManager(Settings.defaults(), bridge(), threaded=False))
    for _ in range(3):
        manager.poll()
    assert [c.args for c in pad.rumble.call_args_list] == [
        controllers.MAGNET_RUMBLE["captured"], controllers.MAGNET_RUMBLE["released"]]
    manager.stop()


def test_rumble_failure_is_harmless(qapp, fake_sdl):
    pad = joystick(1)  # no rumble attribute at all
    fake_sdl.append(pad)
    manager = ControllerManager(Settings.defaults(), bridge(), threaded=False)
    manager._rumble(next(iter(manager.controllers)), "captured")
    manager.stop()


def test_no_rumble_when_haptics_are_disabled_in_the_profile(qapp, fake_sdl, monkeypatch):
    from unittest.mock import Mock
    pad = joystick(1)
    pad.get_axis = lambda index: 0.8 * 32767 if index == 0 else 0
    pad.rumble = Mock()
    fake_sdl.append(pad)
    monkeypatch.setattr(controllers.windows, "move", lambda *_args: "captured")
    settings = Settings.defaults()
    settings.profiles["Default"].magnet_haptics = False
    manager = at_rest(ControllerManager(settings, bridge(), threaded=False))
    manager.poll()
    pad.rumble.assert_not_called()
    manager.stop()


def test_without_automatic_mode_the_magnet_only_works_while_zr_is_held(
        qapp, fake_sdl, monkeypatch):
    trigger = [0.0]
    pad = joystick(1)
    pad.get_axis = lambda index: {0: 0.8, 5: trigger[0]}.get(index, 0) * 32767
    fake_sdl.append(pad)
    strengths = []
    monkeypatch.setattr(controllers.windows, "move",
                        lambda _dx, _dy, strength, *_args: strengths.append(strength))
    settings = Settings.defaults()
    settings.profiles["Default"].magnet_auto = False
    manager = at_rest(ControllerManager(settings, bridge(), threaded=False))
    manager.poll()
    trigger[0] = 1.0
    manager.poll()
    trigger[0] = 0.0
    manager.poll()
    assert strengths == [0, 50, 0]
    manager.stop()


def test_stick_off_center_at_connection_is_ignored_until_seen_at_rest(
        qapp, fake_sdl, monkeypatch):
    # Switch Pro over SDL: a stale off-center position right after connecting
    # used to drive the pointer until the stick was touched.
    left_x = [0.5]
    pad = joystick(1)
    pad.get_axis = lambda index: left_x[0] * 32767 if index == 0 else 0
    fake_sdl.append(pad)
    moves = []
    monkeypatch.setattr(controllers.windows, "move", lambda dx, *_args: moves.append(dx))
    manager = ControllerManager(Settings.defaults(), bridge(), threaded=False)
    for _ in range(3):
        manager.poll()
    assert moves == []
    left_x[0] = 0.05  # back inside the deadzone: the stick is now trusted
    manager.poll()
    left_x[0] = 0.8
    manager.poll()
    assert len(moves) == 1 and moves[0] > 0
    manager.stop()


def test_stale_right_stick_does_not_scroll_until_seen_at_rest(qapp, fake_sdl, monkeypatch):
    pad = joystick(1)
    pad.get_axis = lambda index: 0.9 * 32767 if index == 3 else 0
    fake_sdl.append(pad)
    scrolls = []
    monkeypatch.setattr(controllers.windows, "scroll", scrolls.append)
    manager = ControllerManager(Settings.defaults(), bridge(), threaded=False)
    for _ in range(20):
        manager.poll()
    assert scrolls == []
    manager.stop()


def test_reconnected_device_must_center_its_sticks_again(qapp, fake_sdl, monkeypatch):
    fake_sdl.append(joystick(1))
    moves = []
    monkeypatch.setattr(controllers.windows, "move", lambda dx, *_args: moves.append(dx))
    manager = at_rest(ControllerManager(Settings.defaults(), bridge(), threaded=False))
    fake_sdl.clear()
    manager.poll()
    stale = joystick(2)  # same pad back, reporting a stale off-center stick
    stale.get_axis = lambda index: 0.5 * 32767 if index == 0 else 0
    fake_sdl.append(stale)
    for _ in range(3):
        manager.poll()
    assert moves == []
    manager.stop()


def test_face_buttons_are_read_by_position_not_by_nintendo_label():
    import os
    assert os.environ["SDL_GAMECONTROLLER_USE_BUTTON_LABELS"] == "0"


def test_live_state_publishes_held_buttons_and_raw_sticks(qapp, fake_sdl, monkeypatch):
    pad = joystick(1)
    pad.get_button = lambda index: 1 if index == 0 else 0  # SDL button 0: SOUTH
    pad.get_axis = lambda index: {0: 0.5, 3: -1.0}.get(index, 0) * 32767
    fake_sdl.append(pad)
    monkeypatch.setattr(controllers.windows, "move", lambda *_args: None)
    manager = ControllerManager(Settings.defaults(), bridge(), threaded=False)
    manager.poll()
    pressed, sticks, _touches = manager.live_state[next(iter(manager.controllers))]
    assert "SOUTH" in pressed
    assert sticks[0] == pytest.approx(0.5, abs=0.01) and sticks[3] == pytest.approx(-1.0, abs=0.01)
    manager.stop()


def test_touchpad_contacts_are_published_until_the_finger_lifts(qapp, fake_sdl, monkeypatch):
    pad = joystick(5)
    fake_sdl.append(pad)
    queue = []
    monkeypatch.setattr(controllers.pygame.event, "get", lambda kinds: [queue.pop(0)] if queue else [])
    manager = ControllerManager(Settings.defaults(), bridge(), threaded=False)
    key = next(iter(manager.controllers))
    def touch(kind, x, y):
        return SimpleNamespace(type=kind, instance_id=5, touchpad=0, finger=0, x=x, y=y)
    queue.append(touch(controllers.pygame.CONTROLLERTOUCHPADDOWN, 0.25, 0.5))
    manager.poll()
    assert manager.live_state[key][2] == ((0, 0.25, 0.5),)
    queue.append(touch(controllers.pygame.CONTROLLERTOUCHPADMOTION, 0.75, 1.2))  # clamped
    manager.poll()
    assert manager.live_state[key][2] == ((0, 0.75, 1.0),)
    queue.append(touch(controllers.pygame.CONTROLLERTOUCHPADUP, 0.75, 1.0))
    manager.poll()
    assert manager.live_state[key][2] == ()
    manager.stop()
