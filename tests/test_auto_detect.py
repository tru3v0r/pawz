"""Auto-detect: geometric rules from auto-detect.json on the bundled silhouettes."""
import json
import xml.etree.ElementTree as ET

import pytest
from PySide6.QtCore import QRectF

from pawz.engine.auto_detect import detect, load_rules
from pawz.ui import artwork_editor
from pawz.ui.artwork_editor import BUNDLED_RULES, InputNamesDialog, elements_of
from pawz.ui.controller_assets import ASSET_DIR
from pawz.ui.windows import dpad_arm


def detected(name: str) -> dict[str, str]:
    path = ASSET_DIR / name
    text = path.read_text(encoding="utf-8")
    tags = {node.get("id"): node.tag.split("}")[-1] for node in ET.fromstring(text).iter() if node.get("id")}
    elements = [(e.id, tags[e.id], e.bounds.x(), e.bounds.y(), e.bounds.width(), e.bounds.height())
                for e in elements_of(text)]
    return {element: name for element, (name, _) in detect(elements, load_rules(BUNDLED_RULES)).items()}


def test_switch_pro_matches_the_names_given_by_hand(qapp):
    # The user's own naming of this file, plus the d-pad and centre buttons.
    assert detected("library/switch-pro.svg") == {
        "circle7838-3": "WEST", "circle7838-3-6": "SOUTH", "circle7910": "NORTH",
        "circle7838-3-9": "EAST", "path7483-4": "RIGHT_STICK", "path7483-4-9": "LEFT_STICK",
        "rect6544": "DPAD", "path7756": "BACK", "circle7838": "START",
        "rect7609": "MISC1", "circle7838-4": "GUIDE"}


@pytest.mark.parametrize("name, expected", [
    ("library/xbox-wireless.svg", {"EAST", "WEST", "NORTH", "SOUTH", "LEFT_STICK", "RIGHT_STICK", "DPAD"}),
    ("library/dualshock-4.svg", {"EAST", "WEST", "NORTH", "SOUTH", "LEFT_STICK", "RIGHT_STICK", "TOUCHPAD",
                                 "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT"}),
    ("library/dualshock-3.svg", {"BACK", "START", "GUIDE"}),
    ("library/steam-controller.svg", {"EAST", "WEST", "NORTH", "SOUTH", "LEFT_STICK"}),
])
def test_other_silhouettes(qapp, name, expected):
    assert expected <= set(detected(name).values())


def test_no_guess_without_a_recognisable_layout(qapp):
    assert detected("library/steam-deck.svg") == {}  # no face-button diamond, no sticks


def test_rules_are_data_and_a_user_copy_wins(tmp_path):
    rules = json.loads(BUNDLED_RULES.read_text(encoding="utf-8"))
    assert [rule["type"] for rule in rules["rules"]][:4] == ["labels", "diamond", "diamond", "sticks"]
    user = tmp_path / "auto-detect.json"
    user.write_text(json.dumps({"rules": [], "min_confidence": 0}), encoding="utf-8")
    assert load_rules(user, BUNDLED_RULES)["rules"] == []
    assert load_rules(tmp_path / "missing.json", BUNDLED_RULES) == rules


def test_dialog_auto_detect_keeps_names_chosen_by_hand(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(artwork_editor, "USER_RULES", tmp_path / "none.json")
    dialog = InputNamesDialog(ASSET_DIR / "library" / "switch-pro.svg")
    qtbot.addWidget(dialog)
    dialog._select("circle7910")  # the top face button, called SOUTH by hand on purpose
    dialog.input_picker.setCurrentIndex(dialog.input_picker.findData("SOUTH"))
    dialog.auto_detect()
    assert dialog.names["circle7910"] == "SOUTH" and "circle7910" not in dialog.confidence
    assert dialog.names["circle7838-3-9"] == "EAST" and 50 <= dialog.confidence["circle7838-3-9"] <= 100
    assert "SOUTH" not in {dialog.names[e] for e in dialog.confidence}
    assert "%" in dialog.assigned.item(0).text() or any(
        "%" in dialog.assigned.item(row).text() for row in range(dialog.assigned.count()))


def test_dpad_arms_split_the_cross_in_thirds():
    cross = QRectF(0, 0, 30, 30)
    up, right = dpad_arm(cross, "DPAD_UP"), dpad_arm(cross, "DPAD_RIGHT")
    assert up.center().x() == pytest.approx(15) and up.top() == pytest.approx(0)
    assert up.bottom() < 15 and up.width() == pytest.approx(30 * 0.36)
    assert right.right() == pytest.approx(30) and right.center().y() == pytest.approx(15)
    assert dpad_arm(cross, "DPAD_DOWN").bottom() == pytest.approx(30)
    assert dpad_arm(cross, "DPAD_LEFT").left() == pytest.approx(0)


def detailed(family=None, with_labels=True) -> dict[str, tuple[str, int]]:
    path = ASSET_DIR / "library" / "switch-pro-detailed.svg"
    elements = elements_of(path.read_text(encoding="utf-8"))
    rows = [(e.id, e.kind, e.bounds.x(), e.bounds.y(), e.bounds.width(), e.bounds.height(),
             e.label if with_labels else None) for e in elements]
    labels = {e.id: e.label for e in elements}
    return {labels[element]: result for element, result in detect(rows, load_rules(BUNDLED_RULES), family).items()}


def test_layer_names_name_everything_including_shoulders_and_triggers(qapp):
    found = detailed("nintendo")
    assert found["ZL Trigger"] == ("LEFT_TRIGGER", 98) and found["ZR Trigger"] == ("RIGHT_TRIGGER", 98)
    assert found["L Bumper"] == ("LEFT_SHOULDER", 98) and found["R Bumper"] == ("RIGHT_SHOULDER", 98)
    assert found["X Button"][0] == "NORTH" and found["A Button"][0] == "EAST"  # Nintendo letters
    assert {name for name, _ in found.values()} >= {"LEFT_STICK", "RIGHT_STICK", "DPAD", "BACK", "START",
                                                     "GUIDE", "MISC1", "SOUTH", "WEST"}
    assert "TOUCHPAD" not in {name for name, _ in found.values()}  # not the shoulders' top strip


def test_letters_need_a_family_and_shoulders_have_a_geometric_rule(qapp):
    assert "X Button" not in detailed(None)  # X is the top button on Nintendo, the left one on Xbox
    geometric = detailed(None, with_labels=False)
    assert geometric["ZL Trigger"][0] == "LEFT_TRIGGER" and geometric["L Bumper"][0] == "LEFT_SHOULDER"
    assert geometric["ZR Trigger"][0] == "RIGHT_TRIGGER" and geometric["R Bumper"][0] == "RIGHT_SHOULDER"


def test_detailed_switch_pro_ships_without_the_nintendo_logo():
    import json
    text = (ASSET_DIR / "library" / "switch-pro-detailed.svg").read_text(encoding="utf-8")
    assert "Nintendo Switch Logo" not in text
    manifest = json.loads((ASSET_DIR / "upstream-manifest.json").read_text())
    record = next(r for r in manifest if r["file"] == "library/switch-pro-detailed.svg")
    assert record["removed_layers"] == ["Nintendo Switch Logo"] and record["upstream_sha256"] != record["sha256"]
