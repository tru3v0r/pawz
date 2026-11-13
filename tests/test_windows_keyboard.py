import ctypes
from ctypes import wintypes
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pawz.engine.magnet import Magnet, Target, pull_delta
from pawz.infra import windows


@pytest.fixture(autouse=True)
def fresh_pointer_state(monkeypatch):
    """The magnet and the sub-pixel residual are module-level: isolate each test."""
    monkeypatch.setattr(windows, "_magnet", Magnet())
    monkeypatch.setattr(windows, "_pointer_residual", windows.SubpixelAccumulator())


def test_open_keyboard_uses_windows_shell_to_launch_keyboard(tmp_path, monkeypatch):
    keyboard = tmp_path / "Windows" / "System32" / "osk.exe"
    keyboard.parent.mkdir(parents=True)
    keyboard.touch()
    startfile = Mock()
    monkeypatch.setenv("WINDIR", str(tmp_path / "Windows"))
    monkeypatch.setattr(windows.os, "startfile", startfile)

    windows.open_keyboard()

    startfile.assert_called_once_with(str(keyboard))


def test_open_keyboard_reports_missing_windows_keyboard(tmp_path, monkeypatch):
    monkeypatch.setenv("WINDIR", str(tmp_path))
    startfile = Mock()
    monkeypatch.setattr(windows.os, "startfile", startfile)

    with pytest.raises(FileNotFoundError, match="Windows on-screen keyboard not found"):
        windows.open_keyboard()
    startfile.assert_not_called()


def test_mouse_button_can_be_held_and_released(monkeypatch):
    send_mouse = Mock()
    monkeypatch.setattr(windows, "send_mouse", send_mouse)

    windows.mouse_button_down("left")
    send_mouse.assert_called_once_with(0x0002)
    windows.mouse_button_up("left")
    assert send_mouse.call_args_list[-1].args == (0x0004,)


@pytest.mark.parametrize(("action", "key"), [("play_pause", 0x20), ("fullscreen", 0x46),
                                               ("subtitles", 0x43)])
def test_youtube_actions_use_expected_hotkeys(monkeypatch, action, key):
    send_keys = Mock()
    monkeypatch.setattr(windows, "send_keys", send_keys)

    windows.perform(action)

    send_keys.assert_called_once_with([(key, 0), (key, 2)])


def test_magnetism_pulls_toward_nearby_target_and_respects_zero_strength():
    full_strength = pull_delta(0, 0, (0, 0), [(100, 0)], 100)
    assert full_strength[0] > 0
    assert pull_delta(0, 0, (0, 0), [(100, 0)], 50)[0] == full_strength[0] / 2
    assert pull_delta(1, 2, (0, 0), [(100, 0)], 0) == (1, 2)
    assert pull_delta(1, 2, (0, 0), [(200, 0)], 100) == (1, 2)


def test_magnetism_snaps_cursor_to_exact_target_on_path(monkeypatch):
    def get_cursor(pointer):
        cursor = ctypes.cast(pointer, ctypes.POINTER(wintypes.POINT)).contents
        cursor.x, cursor.y = 5, 5
        return True

    set_cursor = Mock(return_value=True)
    mouse_event = Mock()
    monkeypatch.setattr(windows, "user32", SimpleNamespace(
        GetCursorPos=Mock(side_effect=get_cursor),
        SetCursorPos=set_cursor,
    ))
    monkeypatch.setattr(windows, "send_mouse", mouse_event)
    monkeypatch.setattr(windows, "_interaction_targets", lambda _point, *_: [(20, 20)])

    windows.move(10, 10, 50)

    set_cursor.assert_called_once_with(20, 20)
    mouse_event.assert_not_called()


def test_magnetism_leaves_current_target_and_snaps_to_next_target(monkeypatch):
    def get_cursor(pointer):
        cursor = ctypes.cast(pointer, ctypes.POINTER(wintypes.POINT)).contents
        cursor.x, cursor.y = 20, 20
        return True

    set_cursor = Mock(return_value=True)
    mouse_event = Mock()
    monkeypatch.setattr(windows, "user32", SimpleNamespace(
        GetCursorPos=Mock(side_effect=get_cursor),
        SetCursorPos=set_cursor,
    ))
    monkeypatch.setattr(windows, "send_mouse", mouse_event)
    monkeypatch.setattr(windows, "_interaction_targets", lambda _point, *_: [(20, 20), (40, 20)])

    windows.move(20, 0, 100)

    set_cursor.assert_called_once_with(40, 20)
    mouse_event.assert_not_called()


def test_magnetism_releases_current_target_when_no_target_is_ahead(monkeypatch):
    def get_cursor(pointer):
        cursor = ctypes.cast(pointer, ctypes.POINTER(wintypes.POINT)).contents
        cursor.x, cursor.y = 20, 20
        return True

    set_cursor = Mock(return_value=True)
    mouse_event = Mock()
    monkeypatch.setattr(windows, "user32", SimpleNamespace(
        GetCursorPos=Mock(side_effect=get_cursor),
        SetCursorPos=set_cursor,
    ))
    monkeypatch.setattr(windows, "send_mouse", mouse_event)
    monkeypatch.setattr(windows, "_interaction_targets", lambda _point, *_: [(20, 20)])

    windows.move(-20, 0, 100)

    set_cursor.assert_not_called()
    mouse_event.assert_called_once_with(0x0001, -20, 0)


def test_magnetism_does_not_pull_back_during_a_sustained_escape(monkeypatch):
    position = [20, 20]

    def get_cursor(pointer):
        cursor = ctypes.cast(pointer, ctypes.POINTER(wintypes.POINT)).contents
        cursor.x, cursor.y = position
        return True

    def move_cursor(_flags, dx, dy):
        position[0] += dx
        position[1] += dy

    mouse_event = Mock(side_effect=move_cursor)
    monkeypatch.setattr(windows, "user32", SimpleNamespace(
        GetCursorPos=Mock(side_effect=get_cursor),
        SetCursorPos=Mock(return_value=True),
    ))
    monkeypatch.setattr(windows, "send_mouse", mouse_event)
    monkeypatch.setattr(windows, "_interaction_targets", lambda _point, *_: [(20, 20)])

    for _ in range(5):
        windows.move(-1, 0, 100)

    assert position == [15, 20]
    assert mouse_event.call_count == 5


def _simulated_cursor(monkeypatch, start, targets):
    """Real move() against a simulated cursor; ``targets(point)`` mimics _interaction_targets."""
    position = list(start)

    def get_cursor(pointer):
        cursor = ctypes.cast(pointer, ctypes.POINTER(wintypes.POINT)).contents
        cursor.x, cursor.y = position
        return True

    def set_cursor(x, y):
        position[:] = [x, y]
        return True

    def send_mouse(_flags, dx=0, dy=0, data=0):
        position[0] += dx
        position[1] += dy

    monkeypatch.setattr(windows, "user32", SimpleNamespace(
        GetCursorPos=Mock(side_effect=get_cursor), SetCursorPos=Mock(side_effect=set_cursor)))
    monkeypatch.setattr(windows, "send_mouse", send_mouse)
    monkeypatch.setattr(windows, "_interaction_targets", lambda point, *_: targets(point))
    monkeypatch.setattr(windows, "_pointer_residual", windows.SubpixelAccumulator())
    return position


def test_magnetism_lets_the_cursor_leave_a_window_edge_diagonally(monkeypatch):
    # Edge targets are projections of the cursor on the edge, so they follow it.
    # Leaving the left edge while drifting down used to re-snap onto the edge.
    position = _simulated_cursor(monkeypatch, (0, 100), lambda point: [(0, point[1])])
    for _ in range(100):
        windows.move(-0.3, 0.1, 50, dt=1 / 250)
    assert position[0] <= -25


@pytest.mark.parametrize(("dx", "dy"), [(-2, 1), (-2, -1), (-1, 0.6), (-3, 3)])
def test_magnetism_lets_the_cursor_escape_an_edge_with_a_real_diagonal(monkeypatch, dx, dy):
    # Same as above with a vertical component large enough to change the rounded
    # projection: the projected target lands one pixel along the edge, "ahead".
    window_left, top, bottom = 0, 0, 1000

    def edges(point):
        _x, y = point
        return [(window_left, min(max(y, top), bottom))]

    position = _simulated_cursor(monkeypatch, (window_left, 500), edges)
    for _ in range(30):
        windows.move(dx, dy, 100, dt=1 / 250)
    assert position[0] <= window_left + dx * 30 / 2


def test_magnetism_pull_is_per_second_not_per_call(monkeypatch):
    def pull_after_half_a_second(hz):
        position = _simulated_cursor(monkeypatch, (0, 0), lambda _point: [(100, 30)])
        for _ in range(hz // 2):
            windows.move(60 / hz, 0, 100, dt=1 / hz)
        return position[1]
    slow, fast = pull_after_half_a_second(60), pull_after_half_a_second(250)
    assert slow > 0
    assert abs(fast - slow) <= 2


def test_magnetism_catches_an_edge_holds_then_lets_go(monkeypatch):
    def edges(point):
        return [Target(0, min(max(point[1], 0), 1000), "vline", 0, 1000)]

    position = _simulated_cursor(monkeypatch, (30, 500), edges)
    def move():
        return windows.move(-2, 0.5, 100, dt=1 / 250, full_speed=50)  # 20 px threshold

    assert move() == "captured"
    assert position == [0, 500]  # caught by the edge from 30 px away
    events = [move() for _ in range(10)]
    assert position[0] == 0 and events == [None] * 10  # held: 20 px of effort, threshold 20 px
    assert position[1] == 505  # gliding along the edge meanwhile
    assert move() == "released"
    assert position[0] == -43  # just outside the 40 px capture zone, not flung away
    for _ in range(10):
        assert move() is None  # no bounce back
    assert position[0] == -63


def test_zero_movement_never_snaps(monkeypatch):
    # Seen in a real trace: ticks with a zero delta skipped the "ahead only" filter
    # and snapped the cursor back to a target it had just escaped from.
    position = _simulated_cursor(monkeypatch, (704, 288), lambda _point: [(704, 300)])
    windows.move(0.0, -0.0, 50, dt=1 / 250)
    assert position == [704, 288]
