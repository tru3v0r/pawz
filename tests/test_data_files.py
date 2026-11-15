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
