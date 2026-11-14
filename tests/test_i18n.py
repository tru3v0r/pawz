"""Interface translations: files kept in sync with the code, and loaded at startup."""
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PySide6.QtCore import QLocale

from pawz import i18n
from pawz.core.models import Settings

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "update-translations.py"


def messages(ts: Path) -> dict[str, str]:
    return {message.findtext("source"): message.findtext("translation") or ""
            for message in ET.parse(ts).iter("message")
            if message.find("translation").get("type") not in ("obsolete", "vanished")}


def translation_files() -> list[Path]:
    return sorted(i18n.TRANSLATIONS_DIR.glob("pawz_*.ts"))


def test_every_offered_language_has_compiled_translations():
    for code in i18n.LANGUAGES:
        if code != i18n.SOURCE_LANGUAGE:
            assert (i18n.TRANSLATIONS_DIR / f"pawz_{code}.ts").is_file()
            assert (i18n.TRANSLATIONS_DIR / f"pawz_{code}.qm").is_file()


def test_translation_files_list_exactly_the_strings_in_the_code(tmp_path):
    import PySide6
    lupdate = Path(PySide6.__file__).parent / "lupdate.exe"
    if not lupdate.exists():
        pytest.skip("pyside6-lupdate not available")
    sources = sorted(str(path) for path in (ROOT / "src" / "pawz").rglob("*.py"))
    fresh = tmp_path / "fresh.ts"
    subprocess.run([str(lupdate), *sources, "-ts", str(fresh)], check=True, capture_output=True)
    expected = set(messages(fresh))
    for ts in translation_files():
        assert set(messages(ts)) == expected, (
            f"{ts.name} is out of date: run python scripts/update-translations.py")


@pytest.mark.parametrize("ts", translation_files(), ids=lambda path: path.name)
def test_translations_are_complete_and_keep_placeholders(ts):
    for source, translation in messages(ts).items():
        assert translation, f"untranslated in {ts.name}: {source!r}"
        assert sorted(re.findall(r"\{\w*\}", source)) == sorted(re.findall(r"\{\w*\}", translation)), source


def test_auto_follows_windows_when_the_language_is_offered():
    assert i18n.resolve("fr") == "fr"
    assert i18n.resolve("en", QLocale(QLocale.Language.French)) == "en"
    assert i18n.resolve("auto", QLocale(QLocale.Language.French, QLocale.Country.Canada)) == "fr"
    assert i18n.resolve("auto", QLocale(QLocale.Language.Japanese)) == "en"
    assert i18n.resolve("klingon", QLocale(QLocale.Language.German)) == "en"


def test_install_switches_the_interface_language(qapp):
    try:
        assert i18n.install(qapp, "fr") == "fr"
        assert i18n.tr("Settings") == "Paramètres"
        assert i18n.tr("Forget “{name}” and remove its profile assignment?").format(name="Pad") == (
            "Oublier « Pad » et supprimer son attribution de profil ?")
        assert QLocale().toString(0.5, "f", 2) == "0,50"
    finally:
        assert i18n.install(qapp, "en") == "en"
    assert i18n.tr("Settings") == "Settings"
    assert QLocale().toString(0.5, "f", 2) == "0.50"


def test_language_setting_round_trips_and_tolerates_bad_values():
    settings = Settings.defaults()
    assert settings.language == "auto"
    settings.language = "fr"
    assert Settings.parse(settings.dump()).language == "fr"
    assert Settings.parse(settings.dump() | {"language": 3}).language == "auto"
    raw = settings.dump()
    raw.pop("language")
    assert Settings.parse(raw).language == "auto"


def test_settings_dialog_offers_languages_and_explains_the_restart(qtbot):
    from pawz.ui.windows import SettingsDialog
    dialog = SettingsDialog(Settings.defaults())
    qtbot.addWidget(dialog)
    assert dialog.tabs.tabText(1) == "DISPLAY"
    picker = dialog.language_picker
    assert [picker.itemData(i) for i in range(picker.count())] == ["auto", "en", "fr"]
    assert picker.itemText(2) == "Français"
    assert dialog.display_note.isHidden() and not dialog.display_changed()
    picker.setCurrentIndex(2)
    assert not dialog.display_note.isHidden() and dialog.display_changed()
    picker.setCurrentIndex(0)
    assert dialog.display_note.isHidden()
