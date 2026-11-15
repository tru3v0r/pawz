"""Bundled data files: every one is valid JSON and follows its folder's schema."""
import json

import pytest

from pawz import applications, data_files

SCHEMA_FOLDERS = sorted(schema.parent.relative_to(data_files.BUNDLED_DATA).as_posix()
                        for schema in data_files.BUNDLED_DATA.rglob("*.schema.json")
                        if schema.name == f"{schema.parent.name}.schema.json")


@pytest.mark.parametrize("path", sorted(data_files.BUNDLED_DATA.rglob("*.json")),
                         ids=lambda path: path.relative_to(data_files.BUNDLED_DATA).as_posix())
def test_every_data_file_is_json(path):
    json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("folder", SCHEMA_FOLDERS)
def test_every_file_follows_its_folder_schema(folder):
    assert data_files.load_folder(folder)


def test_a_file_that_breaks_its_schema_is_reported_with_its_path(tmp_path, monkeypatch):
    folder = tmp_path / "things"
    folder.mkdir()
    (folder / "things.schema.json").write_text('{"type": "object", "required": ["name"]}')
    (folder / "broken.json").write_text("{}")
    monkeypatch.setattr(data_files, "BUNDLED_DATA", tmp_path)
    with pytest.raises(data_files.DataError, match=r"broken\.json"):
        data_files.load_folder.__wrapped__("things")


def test_known_applications():
    assert set(applications.BROWSER_PROCESSES) == {"brave.exe", "chrome.exe", "firefox.exe", "msedge.exe"}
    assert {"vlc.exe", "explorer.exe", "pawz.exe"} <= applications.NEVER_GAMES
    assert applications.display_name("VLC.exe") == "VLC"
    assert applications.display_name("C:/Games/some-game.exe") == "some-game"
    assert applications.install_paths("vlc.exe") == ("VideoLAN/VLC/vlc.exe",)


def test_every_key_named_in_the_data_exists():
    from pawz.core.models import default_shortcuts
    from pawz.engine.actions import CATALOGUE
    from pawz.infra.windows import key_code
    combos = [action.keys for action in CATALOGUE if action.keys]
    combos += [binding.keys for group in default_shortcuts() for binding in group.bindings.values()
               if binding.keys]
    for combo in combos:
        for token in combo.split("+"):
            key_code(token)  # raises on an unknown key


def test_data_labels_are_marked_for_translation(tmp_path):
    stub = data_files.write_translation_stub(tmp_path / "labels.py").read_text(encoding="utf-8")
    assert 'QT_TR_NOOP("Left click")' in stub and 'QT_TR_NOOP("Toggle game mode")' in stub


@pytest.mark.parametrize("path", sorted(path for path in data_files.BUNDLED_DATA.rglob("*.json")
                                        if not path.name.endswith(".schema.json")),
                         ids=lambda path: path.relative_to(data_files.BUNDLED_DATA).as_posix())
def test_every_file_follows_its_own_schema(path):
    data_files.load(path.relative_to(data_files.BUNDLED_DATA).as_posix())


def test_controller_data_points_at_existing_models_and_drawings():
    from pawz.core.controller_catalog import load_builtin_catalog
    from pawz.ui.controller_assets import ASSET_DIR
    models = {model.id for model in load_builtin_catalog()}
    identification = data_files.load("controllers/identification.json")
    assert set(identification["usb_ids"]) <= models
    assert {model for _, model in identification["name_hints"]} <= models
    prompts = data_files.load("controllers/prompts.json")
    assert set(prompts["models"]) <= models
    icons = [*prompts["default"].values(), *prompts["face_positions"].values(),
             *(icon for table in (*prompts["families"].values(), *prompts["models"].values())
               for icon in table.values())]
    icons += [prompts["printed_letter"]["pattern"].format(label=letter)
              for letter in prompts["printed_letter"]["letters"]]
    for icon in icons:
        assert (ASSET_DIR / icon).is_file(), icon
    artwork = data_files.load("controllers/artwork.json")
    for drawing in [*artwork["family_silhouettes"].values(), *artwork["asset_pack_files"]]:
        assert (ASSET_DIR / drawing).is_file(), drawing
