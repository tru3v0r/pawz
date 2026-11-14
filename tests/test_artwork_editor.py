"""Naming the inputs of a controller drawing, and where the renamed files go."""
import pytest
from PySide6.QtCore import QPointF

from pawz.core.controller_catalog import load_builtin_catalog
from pawz.ui import artwork_editor, controller_assets
from pawz.ui.artwork_editor import InputNamesDialog, elements_of, rename_element
from pawz.ui.controller_assets import ASSET_DIR, resolve_artwork

SWITCH_PRO = ASSET_DIR / "library" / "switch-pro.svg"


@pytest.fixture
def folders(tmp_path, monkeypatch):
    overrides, export = tmp_path / "artwork", tmp_path / "asset-pack-names"
    monkeypatch.setattr(controller_assets, "OVERRIDES_DIR", overrides)
    monkeypatch.setattr(artwork_editor, "OVERRIDES_DIR", overrides)
    monkeypatch.setattr(artwork_editor, "ASSET_PACK_EXPORT_DIR", export)
    return overrides, export


def test_renaming_changes_only_the_id_and_label():
    text = SWITCH_PRO.read_text(encoding="utf-8")
    renamed = rename_element(text, "circle7838", "SOUTH")
    changed = [(a, b) for a, b in zip(text.splitlines(), renamed.splitlines()) if a != b]
    assert len(changed) == 1
    assert 'id="SOUTH"' in changed[0][1] and 'inkscape:label="SOUTH"' in changed[0][1]
    with pytest.raises(KeyError):
        rename_element(text, "missing", "SOUTH")


def test_elements_are_found_with_their_drawn_bounds(qapp):
    elements = {element.id: element for element in elements_of(SWITCH_PRO.read_text(encoding="utf-8"))}
    assert "path6046" in elements and "circle7838" in elements  # body and a button
    assert elements["circle7838"].bounds.width() < elements["path6046"].bounds.width() / 5


def test_naming_a_bundled_drawing_saves_a_used_copy_and_an_asset_pack_copy(qtbot, folders):
    overrides, export = folders
    dialog = InputNamesDialog(SWITCH_PRO)
    qtbot.addWidget(dialog)
    dialog.resize(760, 460)
    dialog.show()
    button = next(element for element in dialog.elements if element.id == "circle7838")
    point = dialog.picker.to_widget(button.bounds).center()
    assert dialog.picker.element_at(QPointF(point)) == "circle7838"  # smallest under the click
    dialog._select("circle7838")
    dialog.input_picker.setCurrentIndex(dialog.input_picker.findData("SOUTH"))
    assert dialog.names == {"circle7838": "SOUTH"}
    dialog.save()
    saved = overrides / "library" / "switch-pro.svg"
    pr_copy = export / "Connection Icon Pack" / "Controller Type" / "SVG" / "VSCView Switch Pro Controller.svg"
    assert 'id="SOUTH"' in saved.read_text(encoding="utf-8")
    assert pr_copy.read_text(encoding="utf-8") == saved.read_text(encoding="utf-8")
    assert 'id="SOUTH"' not in SWITCH_PRO.read_text(encoding="utf-8")  # bundled file untouched
    model = next(m for m in load_builtin_catalog() if m.id == "nintendo.switch-pro")
    assert resolve_artwork(model) == saved  # pawz now uses the named copy


def test_imported_illustrations_are_renamed_in_place(qtbot, folders, tmp_path):
    own = tmp_path / "mine.svg"
    own.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
                   '<circle id="c1" cx="5" cy="5" r="3"/></svg>', encoding="utf-8")
    dialog = InputNamesDialog(own)
    qtbot.addWidget(dialog)
    assert dialog.relative is None and not dialog.open_folder.isVisibleTo(dialog)
    dialog._select("c1")
    dialog.input_picker.setCurrentIndex(dialog.input_picker.findData("LEFT_STICK"))
    dialog.save()
    assert 'id="LEFT_STICK"' in own.read_text(encoding="utf-8")
    assert not folders[0].exists()
