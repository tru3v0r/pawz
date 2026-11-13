"""Game mode: pawz steps aside for games."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pawz.core import controllers
from pawz.core.controllers import ControllerManager
from pawz.core.models import Settings
from pawz.engine.game_mode import is_game


def rules(**overrides):
    return {"auto": True, "games": [], "non_games": [], "override": None} | overrides


@pytest.mark.parametrize(("app", "fullscreen", "options", "expected"), [
    ("game.exe", True, rules(), True),
    ("game.exe", False, rules(), False),
    ("game.exe", True, rules(auto=False), False),
    ("firefox.exe", True, rules(), False),  # full-screen video stays controllable
    ("tool.exe", True, rules(non_games=["tool.exe"]), False),
    ("windowed.exe", False, rules(games=["windowed.exe"]), True),
    ("game.exe", True, rules(override=("game.exe", False)), False),
    ("other.exe", False, rules(override=("game.exe", True)), False),  # override of another app
    ("", True, rules(), False),
])
def test_game_rules(app, fullscreen, options, expected):
    assert is_game(app, fullscreen, **options) is expected


def test_settings_round_trip_and_validate():
    settings = Settings.defaults()
    settings.game_mode_auto, settings.games = False, ["elden.exe"]
    parsed = Settings.parse(settings.dump())
    assert (parsed.game_mode_auto, parsed.games, parsed.non_games) == (False, ["elden.exe"], [])
    raw = settings.dump() | {"games": "elden.exe"}
    with pytest.raises(ValueError, match="games"):
        Settings.parse(raw)


def test_defaults_bind_the_toggle_and_the_edit_layer():
    bindings = Settings.defaults().profiles["Default"].global_bindings
    assert bindings["BACK+START"].action == "game_mode"
    assert (bindings["EAST+LEFT_TRIGGER"].action, bindings["EAST+LEFT_TRIGGER"].keys) == (
        "key_combo", "ctrl+y")
    assert bindings["DPAD_UP+LEFT_TRIGGER"].keys == "shift+up"


@pytest.fixture
def game_manager(qapp, monkeypatch):
    monkeypatch.setattr(controllers.windows, "active_process", lambda: "game.exe")
    monkeypatch.setattr(controllers.windows, "foreground_fullscreen", lambda: True)
    manager = ControllerManager(Settings.defaults(), SimpleNamespace(domain=lambda _a: ""),
                                threaded=False, output=Mock())
    yield manager
    manager.stop()


def test_full_screen_game_silences_pawz_but_not_the_toggle(game_manager):
    manager = game_manager
    changes = []
    manager.game_mode_changed.connect(changes.append)
    manager._check_game_mode(10.0)
    assert manager.game_active and changes == [True]
    manager._press_button("pad", "EAST", 10.1)  # left click: swallowed
    manager._release_button("pad", "EAST")
    assert manager.output.mock_calls == []
    manager._press_button("pad", "BACK", 10.2)  # BACK+START: back to pawz
    manager._press_button("pad", "START", 10.3)
    assert not manager.game_active and changes == [True, False]
    manager._check_game_mode(11.0)  # the manual choice holds while the game is in front
    assert not manager.game_active


def test_entering_game_mode_lets_go_of_a_held_click(game_manager):
    manager = game_manager
    manager._press_button("pad", "EAST", 1.0)
    manager.output.mouse_down.assert_called_once_with("left")
    manager._check_game_mode(10.0)
    manager.output.mouse_up.assert_called_once_with("left")
    manager._release_button("pad", "EAST")
    assert manager.output.mouse_up.call_count == 1


def test_game_mode_options_in_general_settings(qapp):
    from pawz.ui.windows import SettingsDialog, executable_list
    assert executable_list(" Elden.exe ; hades.exe,, ") == ["elden.exe", "hades.exe"]
    dialog = SettingsDialog(Settings.defaults())
    assert dialog.game_auto_checkbox.isChecked()
    assert dialog.games_edit.text() == ""
