import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QComboBox, QDialog, QLineEdit, QPushButton

from pawz.core.controller_catalog import ControllerCatalog, load_builtin_catalog
from pawz.core.controller_services import (
    Calibration,
    DeviceIdentityRegistry,
    read_raw,
    resolve_model,
    validate_mapping,
)
from pawz.core.controllers import ControllerManager
from pawz.core.models import SYSTEM_DEFAULT_PROFILE_ID, Binding, Settings
from pawz.engine.gestures import GestureEngine, MouseUp
from pawz.infra.storage import load, save
from pawz.ui.controller_assets import SvgView, resolve_artwork
from pawz.ui.windows import CSS, SettingsDialog


def test_system_profile_protected_after_rename_and_duplicate_roundtrip():
    settings = Settings.defaults()
    copy = settings.duplicate_profile("Default", "Guest")
    assert copy.profile_id != SYSTEM_DEFAULT_PROFILE_ID
    settings.rename_profile("Default", "System")
    settings = Settings.parse(settings.dump())
    with pytest.raises(ValueError, match="cannot be removed"):
        settings.remove_profile("System")
    settings.remove_profile("Guest")


def test_duplicate_preserves_contexts_but_is_independent():
    settings = Settings.defaults()
    guest = settings.duplicate_profile("Default", "Guest")
    assert guest.sites == settings.profiles["Default"].sites
    guest.sites["youtube.com"]["WEST"].action = "win"
    assert settings.profiles["Default"].sites["youtube.com"]["WEST"].action == "play_pause"


def test_migration_is_reproducible_idempotent_backed_up_and_lossless(tmp_path):
    raw = {"schema_version": 1, "profiles": {
        "Default": {"global_bindings": {"a": "left_click"}},
        "Guest": {"sites": {"youtube.com": {"a+l": {"action": "key_combo", "keys": "ctrl+t"}}}},
    }, "assignments": {"guid#1": "Guest"}}
    path = tmp_path / "settings.json"
    payload = json.dumps(raw)
    path.write_text(payload)
    assert Settings.parse(raw).dump() == Settings.parse(raw).dump()
    settings = load(path)
    backup = path.with_suffix(".json.v1.bak")
    assert backup.read_text() == payload
    assert settings.assignments == raw["assignments"]
    assert settings.profiles["Guest"].resolve("SOUTH+LEFT_SHOULDER", domain="youtube.com").keys == "ctrl+t"
    assert load(path).dump() == settings.dump()
    assert backup.read_text() == payload
    assert raw["schema_version"] == 1


def test_preferences_mapping_and_display_model_persist_separately(tmp_path):
    settings = Settings.defaults()
    settings.browser_token = "test-token"
    settings.known_devices = {"device-1": "Nintendo Switch Pro Controller"}
    settings.device_preferences = {"device-1": {"name": "Battletron Pro Controller", "model_id": "nintendo.switch-pro", "guid": "a"*32}}
    settings.controller_mappings = {"device-1": {"SOUTH": "b5", "LEFT_X": "a0"}}
    settings.display_controller_model = "sony.dualsense"
    path = tmp_path / "settings.json"
    save(settings, path)
    assert load(path).dump() == settings.dump()


def test_identical_guid_devices_keep_instance_identity_when_first_disconnects():
    registry = DeviceIdentityRegistry()
    known = {"same#0": "First", "same#1": "Second"}
    first = registry.acquire(101, "same", known, {}, set())
    second = registry.acquire(202, "same", known, {}, {first})
    assert first != second
    registry.retain({202})
    assert registry.acquire(202, "same", known, {}, set()) == second
    third = registry.acquire(303, "same", known, {}, {second})
    assert third != second


def test_new_devices_get_distinct_saved_ids():
    registry = DeviceIdentityRegistry()
    first = registry.acquire(1, "same", {}, {}, set())
    second = registry.acquire(2, "same", {}, {}, {first})
    assert first != second


def test_model_resolution_manual_override_guid_and_safe_fallback(tmp_path):
    catalog = ControllerCatalog(tmp_path / "catalog.json")
    custom = replace(catalog.definitions[0], id="custom.test", known_guids=("a"*32,))
    catalog.add_custom(custom)
    assert resolve_model(catalog.definitions, "a"*32, "Unknown") == custom.id
    assert resolve_model(catalog.definitions, "a"*32, "Unknown", "sony.dualsense") == "sony.dualsense"
    assert resolve_model(catalog.definitions, "b"*32, "Battletron") == "generic.sdl-gamecontroller"


class Joystick:
    buttons = [0, 0]
    axes = [0.0, -1.0]
    hat = (0, 0)

    def get_numbuttons(self): return 2
    def get_numaxes(self): return 2
    def get_numhats(self): return 1
    def get_button(self, index): return self.buttons[index]
    def get_axis(self, index): return self.axes[index]
    def get_hat(self, index): return self.hat


def test_calibration_reads_raw_buttons_hat_and_analog_trigger():
    joy = Joystick()
    calibration = Calibration(joy)
    joy.buttons = [0, 1]
    assert calibration.capture("SOUTH") == "b1"
    calibration.baseline = calibration.snapshot()
    joy.hat = (-1, 0)
    assert calibration.capture("DPAD_LEFT") == "h0.8"
    calibration.baseline = calibration.snapshot()
    joy.axes = [0, 1]
    assert calibration.capture("LEFT_TRIGGER") == "a1"
    assert read_raw(joy, "a1") == 1
    assert read_raw(joy, "-a1") == 0


@pytest.mark.parametrize("mapping", [{"A": "b0"}, {"SOUTH": -1}, {"SOUTH": "b-1"}, {"LEFT_X": "unknown"}, []])
def test_invalid_mappings_rejected(mapping):
    with pytest.raises(ValueError):
        validate_mapping(mapping)


def test_release_combo_is_isolated_by_device():
    engine = GestureEngine()
    for device, action in (("first", "left_click"), ("second", "right_click")):
        engine.press(device, "SOUTH", 0, {"SOUTH+EAST": action})
        engine.press(device, "EAST", 0, {"SOUTH+EAST": action})
    assert engine.release("first", "SOUTH") == [MouseUp("first", "left")]
    assert "SOUTH+EAST" in engine.device("second").combo_clicks


def test_three_tabs_default_protection_and_display_change(qtbot, qapp, tmp_path, monkeypatch):
    monkeypatch.setattr("pawz.ui.windows.DATA_DIR", tmp_path)
    qapp.setStyleSheet(CSS)
    settings = Settings.defaults()
    original = settings.profiles["Default"].dump()
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)
    assert [dialog.tabs.tabText(i) for i in range(5)] == ["GENERAL", "DISPLAY", "PROFILES", "CONTROLLERS", "ABOUT"]
    assert not dialog.findChild(QPushButton, "deleteProfile").isEnabled()
    assert all(dialog.findChild(QPushButton, name) for name in ("duplicateProfile", "renameProfile", "deleteProfile"))
    dialog.tabs.setCurrentIndex(2)
    dialog.show()
    qtbot.wait(20)
    before = dialog.profile_editor.findChild(SvgView, "bindingPrompt").grab().toImage()
    picker = dialog.findChild(QComboBox, "displayControllerModel")
    picker.setCurrentIndex(picker.findData("sony.dualsense"))
    qtbot.wait(20)
    after = dialog.profile_editor.findChild(SvgView, "bindingPrompt").grab().toImage()
    assert before != after
    assert dialog.profile_editor.profile.dump() == original
    assert dialog.settings.display_controller_model == "sony.dualsense"
    assert settings.display_controller_model != "sony.dualsense"
    for width in (708, 900):
        dialog.resize(width, 720)
        qtbot.wait(20)
        rows = dialog.profile_editor.findChildren(SvgView, "bindingPrompt")
        assert all(row.width() == 96 and row.renderer.isValid() for row in rows)


def test_svg_fallback_invalid_custom_and_physical_labels(qapp, tmp_path):
    models = {model.id: model for model in load_builtin_catalog()}
    assert models["nintendo.switch-pro"].physical_labels["SOUTH"] == "B"
    assert models["microsoft.xbox-one"].physical_labels["SOUTH"] == "A"
    invalid = tmp_path / "bad.svg"
    invalid.write_text("invalid")
    assert resolve_artwork(models["sony.dualsense"], str(invalid)).name == "dualsense-detailed.svg"
    assert resolve_artwork(models["sony.dualsense"], "asset:xbox.svg").name == "xbox.svg"


def test_pencil_edits_action_chord_and_moves_context_without_losing_other_bindings(qtbot, monkeypatch):
    dialog = SettingsDialog(Settings.defaults())
    qtbot.addWidget(dialog)
    editor = dialog.profile_editor
    existing_site = dict(editor.profile.sites["youtube.com"])
    def edit(edit_dialog):
        edit_dialog.findChild(QLineEdit, "bindingLogicalInput").setText("SOUTH+LEFT_SHOULDER")
        action = edit_dialog.findChild(QComboBox, "bindingWindowsAction")
        action.setCurrentIndex(action.findData("key_combo"))
        # Context and keys controls belong to this real editor dialog.
        lines = edit_dialog.findChildren(QLineEdit)
        lines[1].setText("ctrl+t")
        lines[2].setText("example.org")
        edit_dialog.findChildren(QComboBox)[1].setCurrentIndex(2)
        next(button for button in edit_dialog.findChildren(QPushButton)
             if button.text() == "Save").click()
        return edit_dialog.result()
    monkeypatch.setattr(QDialog, "exec", edit)
    editor.edit_binding(editor.profile.global_bindings, "WEST")
    assert "WEST" not in editor.profile.global_bindings
    assert editor.profile.sites["youtube.com"] == existing_site
    assert editor.profile.resolve("SOUTH+LEFT_SHOULDER", domain="example.org") == Binding("key_combo", "ctrl+t")


def test_hotplug_keeps_survivor_identity_and_releases_only_removed_device(qapp, tmp_path, monkeypatch):
    from pawz.core import controllers
    def joystick(instance):
        return SimpleNamespace(
            init=lambda: None, get_guid=lambda: "f"*32, get_instance_id=lambda: instance,
            get_name=lambda: "Identical controller", get_power_level=lambda: "full",
            get_button=lambda _index: 0, get_axis=lambda _index: 0,
        )
    connected = [joystick(10), joystick(20)]
    monkeypatch.setattr(controllers, "DATA_DIR", tmp_path)
    monkeypatch.setattr(controllers.pygame, "init", lambda: None)
    monkeypatch.setattr(controllers.pygame.joystick, "init", lambda: None)
    monkeypatch.setattr(controllers.pygame.event, "pump", lambda: None)
    monkeypatch.setattr(controllers.pygame.joystick, "get_count", lambda: len(connected))
    monkeypatch.setattr(controllers.pygame.joystick, "Joystick", lambda index: connected[index])
    monkeypatch.setattr(controllers.sdl_controller, "init", lambda: None)
    monkeypatch.setattr(controllers.sdl_controller, "is_controller", lambda index: True)
    monkeypatch.setattr(controllers.sdl_controller, "Controller", lambda index: connected[index])
    monkeypatch.setattr(controllers.windows, "active_process", lambda: "")
    released = []
    monkeypatch.setattr(controllers.windows, "mouse_button_up", released.append)
    manager = ControllerManager(Settings.defaults(), SimpleNamespace(domain=lambda _: ""),
                                threaded=False)
    first, second = list(manager.controllers)
    for device, mouse in ((first, "left"), (second, "right")):
        state = manager.gestures.device(device)
        state.pressed["SOUTH"] = 1
        state.combo_clicks["SOUTH+EAST"] = mouse
        state.fired_combos.add("SOUTH+EAST")
    connected.pop(0)
    manager.refresh()
    assert list(manager.controllers) == [second]
    assert released == ["left"]
    assert manager.gestures.is_pressed(second, "SOUTH")
    assert "SOUTH+EAST" in manager.gestures.device(second).combo_clicks
    # A replacement at equal count must still be detected by instance identity.
    connected[0] = joystick(30)
    manager.poll()
    assert set(manager.identities.instances) == {30}
    assert released == ["left", "right"]
