"""Table-driven rules of the gesture engine (no hardware, Qt or Windows)."""
import pytest

from pawz.engine.gestures import (
    LONG_PRESS_DELAY,
    CaptureInput,
    Dispatch,
    GestureEngine,
    LongPress,
    MouseDown,
    MouseUp,
)

D = "pad"
ACTIONS = {
    "SOUTH": "key_combo",
    "WEST": "left_click",
    "LEFT_SHOULDER": "previous",
    "SOUTH+LEFT_SHOULDER": "tab_previous",
    "NORTH+EAST": "right_click",
    "NORTH": "none",
    "GUIDE": "win",
}

# Each step: (operation, button, time, expected effects)
SCENARIOS = {
    "plain button acts on release": [
        ("press", "EAST", 0, []),
        ("release", "EAST", 0.1, [Dispatch(D, "EAST")]),
    ],
    "click is held from press to release": [
        ("press", "WEST", 0, [MouseDown(D, "left")]),
        ("release", "WEST", 0.5, [MouseUp(D, "left")]),
    ],
    "chord fires once and consumes its buttons": [
        ("press", "SOUTH", 0, []),
        ("press", "LEFT_SHOULDER", 0.05, [Dispatch(D, "SOUTH+LEFT_SHOULDER")]),
        ("release", "SOUTH", 0.2, []),
        ("release", "LEFT_SHOULDER", 0.2, []),
    ],
    "chord member alone acts on release": [
        ("press", "SOUTH", 0, []),
        ("release", "SOUTH", 0.1, [Dispatch(D, "SOUTH")]),
    ],
    "chord can fire again after a release": [
        ("press", "SOUTH", 0, []),
        ("press", "LEFT_SHOULDER", 0, [Dispatch(D, "SOUTH+LEFT_SHOULDER")]),
        ("release", "LEFT_SHOULDER", 0.1, []),
        ("press", "LEFT_SHOULDER", 0.2, [Dispatch(D, "SOUTH+LEFT_SHOULDER")]),
    ],
    "click chord holds until any member is released": [
        ("press", "NORTH", 0, []),
        ("press", "EAST", 0, [MouseDown(D, "right")]),
        ("release", "EAST", 0.3, [MouseUp(D, "right")]),
        ("release", "NORTH", 0.4, []),
    ],
    "long press fires once and suppresses release": [
        ("press", "GUIDE", 0, []),
        ("tick", None, LONG_PRESS_DELAY - 0.01, []),
        ("tick", None, LONG_PRESS_DELAY, [LongPress(D, "GUIDE")]),
        ("tick", None, 2, []),
        ("release", "GUIDE", 2, []),
    ],
    "short press of a long-press button acts on release": [
        ("press", "GUIDE", 0, []),
        ("tick", None, 0.3, []),
        ("release", "GUIDE", 0.3, [Dispatch(D, "GUIDE")]),
    ],
}


@pytest.mark.parametrize("steps", SCENARIOS.values(), ids=SCENARIOS.keys())
def test_gesture_rules(steps):
    engine = GestureEngine()
    for operation, button, now, expected in steps:
        if operation == "press":
            effects = engine.press(D, button, now, ACTIONS)
        elif operation == "release":
            effects = engine.release(D, button)
        else:
            effects = engine.tick(D, now)
        assert effects == expected, (operation, button, now)


def test_long_press_is_ignored_for_chord_members():
    engine = GestureEngine()
    actions = {**ACTIONS, "GUIDE+SOUTH": "win"}
    engine.press(D, "GUIDE", 0, actions)
    assert engine.tick(D, 5) == []
    assert engine.release(D, "GUIDE") == [Dispatch(D, "GUIDE")]


def test_capture_reports_inputs_instead_of_acting():
    engine = GestureEngine()
    engine.begin_capture()
    assert engine.press(D, "WEST", 0, ACTIONS) == [CaptureInput(D, "WEST", True)]
    assert engine.release(D, "WEST") == [CaptureInput(D, "WEST", False)]
    engine.end_capture()
    assert engine.press(D, "WEST", 1, ACTIONS) == [MouseDown(D, "left")]


def test_capture_releases_held_clicks_and_neutralizes_held_buttons():
    engine = GestureEngine()
    engine.press(D, "WEST", 0, ACTIONS)
    engine.press(D, "EAST", 0, ACTIONS)
    assert engine.begin_capture() == [MouseUp(D, "left")]
    engine.end_capture()
    assert engine.release(D, "WEST") == []
    assert engine.release(D, "EAST") == []


def test_capture_during_chord_does_not_leave_stale_state():
    engine = GestureEngine()
    engine.press(D, "SOUTH", 0, ACTIONS)
    engine.press(D, "LEFT_SHOULDER", 0, ACTIONS)
    engine.begin_capture()
    engine.release(D, "SOUTH")
    engine.release(D, "LEFT_SHOULDER")
    engine.end_capture()
    engine.press(D, "SOUTH", 1, ACTIONS)
    assert engine.release(D, "SOUTH") == [Dispatch(D, "SOUTH")]


def test_removed_device_releases_everything_it_held():
    engine = GestureEngine()
    engine.press(D, "WEST", 0, ACTIONS)
    engine.press(D, "NORTH", 0, ACTIONS)
    engine.press(D, "EAST", 0, ACTIONS)
    assert sorted(engine.remove_device(D), key=repr) == [MouseUp(D, "left"), MouseUp(D, "right")]
    assert not engine.is_pressed(D, "WEST")
    assert engine.remove_device(D) == []


def test_devices_are_independent():
    engine = GestureEngine()
    engine.press("a", "SOUTH", 0, ACTIONS)
    assert engine.press("b", "LEFT_SHOULDER", 0, ACTIONS) == []
    assert engine.release("a", "SOUTH") == [Dispatch("a", "SOUTH")]


def test_engine_package_stays_pure():
    import ast
    from pathlib import Path

    import pawz.engine as engine_package

    forbidden = ("PySide6", "pygame", "ctypes", "pawz.infra", "pawz.ui")
    for path in Path(engine_package.__file__).parent.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                     else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            for name in names:
                assert not name.startswith(forbidden), f"{path.name} imports {name}"


LAYER = {"EAST": "left_click", "LEFT_TRIGGER+EAST": "key_combo",
         "LEFT_TRIGGER+SOUTH": "key_combo", "SOUTH": "right_click"}


def test_layer_button_does_not_delay_the_plain_click():
    engine = GestureEngine()
    assert engine.press(D, "EAST", 0, LAYER) == [MouseDown(D, "left")]
    assert engine.release(D, "EAST") == [MouseUp(D, "left")]


def test_layer_binding_fires_when_the_layer_is_held_first():
    engine = GestureEngine()
    assert engine.press(D, "LEFT_TRIGGER", 0, LAYER) == []
    assert engine.press(D, "EAST", 0.1, LAYER) == [Dispatch(D, "LEFT_TRIGGER+EAST")]
    assert engine.release(D, "EAST") == []
    # Still in the layer: another button uses it too.
    assert engine.press(D, "SOUTH", 0.2, LAYER) == [Dispatch(D, "LEFT_TRIGGER+SOUTH")]
    assert engine.release(D, "SOUTH") == []
    assert engine.release(D, "LEFT_TRIGGER") == []  # used as a modifier: consumed


def test_pressing_the_layer_after_the_button_keeps_the_click():
    engine = GestureEngine()
    assert engine.press(D, "EAST", 0, LAYER) == [MouseDown(D, "left")]
    assert engine.press(D, "LEFT_TRIGGER", 0.1, LAYER) == []
    assert engine.release(D, "EAST") == [MouseUp(D, "left")]


def test_release_clicks_lets_go_and_makes_held_buttons_inert():
    engine = GestureEngine()
    engine.press(D, "EAST", 0, LAYER)
    engine.press(D, "NORTH", 0, {"NORTH": "key_combo"})
    assert engine.release_clicks() == [MouseUp(D, "left")]
    assert engine.release(D, "EAST") == []
    assert engine.release(D, "NORTH") == []
