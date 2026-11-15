import json
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontInfo, QIcon
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QSlider, QWidget

from pawz.core.controller_catalog import load_builtin_catalog
from pawz.core.models import Settings
from pawz.ui import windows
from pawz.ui.controller_assets import ASSET_DIR, SvgView, prompt_path


def test_all_fonts_registered_from_bundle_without_system_font_lookup(qapp, monkeypatch):
    registered = []
    original = QFontDatabase.addApplicationFont
    def register(path):
        registered.append(Path(path))
        return original(path)
    monkeypatch.setattr(QFontDatabase, "addApplicationFont", register)
    def system_lookup():
        raise AssertionError("Bundled fonts must not depend on installed-font discovery")
    monkeypatch.setattr(QFontDatabase, "families", system_lookup)
    windows._LOADED_FONT_PATHS.clear()
    windows.load_fonts()
    assert {path.name for path in registered} == {"Inter-Regular.ttf", "Inter-SemiBold.ttf", "MatchaStyle.ttf"}
    assert all(path.parent == windows.ASSETS_DIR / "fonts" for path in registered)
    assert QFontInfo(QFont("Matcha Style", 12)).family() == "Matcha Style"
    assert QFontInfo(QFont("Inter 18pt", 12)).family() == "Inter 18pt"


def test_icon_buttons_have_no_text_and_keep_labels_and_disabled_state(qtbot):
    dialog = windows.SettingsDialog(Settings.defaults())
    qtbot.addWidget(dialog)
    for name, title in (("duplicateProfile", "Duplicate"), ("renameProfile", "Rename"), ("deleteProfile", "Delete"),
                        ("duplicateControllerModel", "Duplicate"), ("editControllerModel", "Edit"), ("deleteControllerModel", "Delete")):
        button = dialog.findChild(QPushButton, name)
        assert button.text() == ""
        assert not button.icon().isNull()
        assert button.toolTip() == button.accessibleName() == title
        normal = button.icon().pixmap(18, 18, QIcon.Mode.Normal).toImage()
        disabled = button.icon().pixmap(18, 18, QIcon.Mode.Disabled).toImage()
        assert normal != disabled
    assert not dialog.delete_profile_button.isEnabled()


def test_unfilled_slider_track_is_dark_blue_and_headers_stay_close(qtbot, qapp):
    qapp.setStyleSheet(windows.CSS)
    dialog = windows.SettingsDialog(Settings.defaults())
    qtbot.addWidget(dialog)
    dialog.tabs.setCurrentIndex(2)
    dialog.show()
    qtbot.wait(20)
    slider = dialog.profile_editor.findChild(QSlider, "mouse_speed")
    slider.setValue(slider.minimum())
    image = slider.grab().toImage()
    assert image.pixelColor(image.width() - 10, image.height() // 2) == QColor("#10233f")
    for header in dialog.profile_editor.findChildren(windows.ProfileSectionHeader):
        icon = header.findChild(QLabel, "profileSectionIcon")
        title = header.findChild(QLabel, "profileSectionTitle")
        if icon:
            assert title.x() - icon.geometry().right() <= 3
            assert title.width() <= title.sizeHint().width()


def test_vendored_prompts_are_used_for_model_and_chords(qtbot):
    models = {model.id: model for model in load_builtin_catalog()}
    assert prompt_path("SOUTH", models["nintendo.switch-pro"]).name == "shared-B-Color.svg"
    assert prompt_path("SOUTH", models["microsoft.xbox-one"]).name == "shared-A-Color.svg"
    assert prompt_path("SOUTH", models["sony.dualsense"]).name == "ps-Cross-Color.svg"
    assert prompt_path("GUIDE", models["sony.dualsense"]) is None
    view = SvgView()
    qtbot.addWidget(view)
    view.set_controller_prompt("SOUTH+LEFT_SHOULDER", models["nintendo.switch-pro"])
    assert view.renderer.isValid()
    assert len(view.property("svgSources")) == 2
    assert all("prompts/" in source.replace("\\", "/") for source in view.property("svgSources"))
    assert view.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert not any("guide" in path.name.lower() for path in (ASSET_DIR / "prompts").rglob("*.svg"))


def test_vendored_resources_match_their_recorded_hashes(qapp):
    import hashlib

    from PySide6.QtSvg import QSvgRenderer
    manifest = json.loads((ASSET_DIR / "upstream-manifest.json").read_text())
    assert sum(record["file"].endswith(".svg") for record in manifest) == 169
    for record in manifest:
        assert hashlib.sha256((ASSET_DIR / record["file"]).read_bytes()).hexdigest() == record["sha256"]
        if record["file"].endswith(".svg"):
            assert QSvgRenderer(str(ASSET_DIR / record["file"])).isValid()


def test_profile_selectors_share_left_edge_and_label(qtbot, qapp):
    qapp.setStyleSheet(windows.CSS)
    dialog = windows.SettingsDialog(Settings.defaults())
    qtbot.addWidget(dialog)
    dialog.tabs.setCurrentIndex(2)
    dialog.show()
    qtbot.wait(20)
    assert dialog.findChild(QLabel, "profilePickerLabel").text() == "Profile"
    assert dialog.profile_picker.x() == dialog.display_model_picker.x()
    assert dialog.profile_picker.width() == dialog.display_model_picker.width()
    assert dialog.findChild(QLabel, "profilePickerLabel").x() == dialog.findChild(QLabel, "displayControllerLabel").x()
    heading = next(heading for heading in dialog.profile_editor.findChildren(windows.ProfileSectionHeading)
                   if heading.label.text() == "SENSITIVITY")
    assert dialog.findChild(QLabel, "profilePickerLabel").mapTo(dialog, QPoint()).x() == heading.label.mapTo(dialog, QPoint()).x()
    for button in dialog.profile_editor.findChildren(QPushButton, "settingsAction"):
        if button.text() in ("Add an application...", "Add a website..."):
            assert button.width() == 2 * button.sizeHint().width()


def test_shortcuts_have_centered_small_colored_prompts_separators_and_bare_actions(qtbot, qapp):
    qapp.setStyleSheet(windows.CSS)
    dialog = windows.SettingsDialog(Settings.defaults())
    qtbot.addWidget(dialog)
    dialog.tabs.setCurrentIndex(2)
    dialog.show()
    qtbot.wait(20)
    for width in (708, 900):
        dialog.resize(width, 760)
        qtbot.wait(20)
        for section in dialog.profile_editor.findChildren(windows.ProfileSectionFrame):
            content = section.findChild(QWidget, "profileSectionContent")
            prompts = content.findChildren(SvgView, "bindingPrompt")
            separators = content.findChildren(QFrame, "bindingRowSeparator")
            assert len(separators) == max(0, len(prompts)-1)
            centers = []
            for prompt in prompts:
                assert prompt.size().toTuple() == (96, 24)
                assert prompt.render_scale == 0.9
                centers.append(prompt.geometry().center().x())
                assert abs(prompt.geometry().center().x() - content.rect().center().x()) <= 40
            assert len(set(centers)) <= 1
            for separator in separators:
                assert separator.height() == 1
                image = separator.grab().toImage()
                assert image.pixelColor(image.width()//2, 0) == QColor("#31557e")
            for name in ("editBinding", "removeBinding"):
                for button in content.findChildren(QPushButton, name):
                    assert button.isFlat()
                    assert button.iconSize().toTuple() == (14, 14)
                    image = button.grab().toImage()
                    corner = image.pixelColor(0, 0)
                    assert corner.alpha() == 0 or corner == QColor("#1b355b")
    model = next(model for model in load_builtin_catalog() if model.id == "microsoft.xbox-one")
    assert prompt_path("SOUTH", model).name == "shared-A-Color.svg"


def test_combinations_leave_a_space_around_the_plus():
    import xml.etree.ElementTree as ET

    from pawz.ui.controller_assets import PROMPT_GAP, controller_prompt_svg
    data, sources = controller_prompt_svg("SOUTH+EAST", None)
    root = ET.fromstring(data)
    assert root.get("viewBox") == f"0 0 {72 + PROMPT_GAP} 36"
    plus = next(node for node in root.iter() if node.tag.endswith("text") and node.text == "+")
    # Centred in the gap, which leaves room on both sides of the 16 px glyph.
    assert float(plus.get("x")) == 36 + PROMPT_GAP / 2 and PROMPT_GAP >= 24
    assert len(sources) == 2
