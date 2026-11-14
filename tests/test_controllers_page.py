from PySide6.QtCore import Qt
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QScrollArea, QWidget

from pawz.core.controller_catalog import load_builtin_catalog
from pawz.core.models import Settings
from pawz.ui.controller_assets import (
    ASSET_DIR,
    PROMPT_ROLE,
    PromptDelegate,
    SvgView,
    prompt_path,
    resolve_artwork,
)
from pawz.ui.controllers_page import SOURCES_ROLE
from pawz.ui.windows import CSS, SettingsDialog, load_fonts


def make_dialog(qtbot):
    settings = Settings.defaults()
    settings.known_devices = {"device": "Xbox 360"}
    settings.device_preferences = {"device": {"guid": "a" * 32, "model_id": "microsoft.xbox-360"}}
    settings.controller_mappings = {"device": {"SOUTH": "b4"}}
    QApplication.instance().setStyleSheet(CSS)
    load_fonts()
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)
    dialog.tabs.setCurrentIndex(3)
    dialog.resize(820, 760)
    dialog.show()
    qtbot.wait(30)
    return dialog


def test_identification_has_real_fields_centered_in_a_centered_table(qtbot):
    dialog = make_dialog(qtbot)
    table = dialog.controllers_page.metadata
    # Drawing (both columns), five fields, custom name.
    assert table.rowCount() == 7 and table.columnCount() == 2
    assert table.columnSpan(0, 0) == 2
    assert [table.field(i, 0).text() for i in range(5)] == ["Manufacturer", "Model", "Family", "SDL GUID", "Status"]
    assert [table.field(i).text() for i in range(5)] == ["Microsoft", "Xbox 360", "xbox", "a"*32, "Not verified on hardware"]
    assert all(table.field(i, col).textAlignment() == Qt.AlignmentFlag.AlignCenter
               for i in range(5) for col in range(2))
    artwork = dialog.controllers_page.artwork
    assert artwork.height() == 75 and artwork.renderer.isValid()
    assert table.rowHeight(0) > artwork.height()  # vertical margin around the drawing
    assert table.item(6, 0).text() == "Custom name"
    assert table.cellWidget(6, 1).isAncestorOf(dialog.controllers_page.name)
    for width in (708, 900):
        dialog.resize(width, 760)
        qtbot.wait(30)
        host = table.parentWidget()
        assert abs(table.geometry().center().x() - host.rect().center().x()) <= 1
        assert table.width() <= host.width()
        assert table.height() >= table.verticalHeader().length()


def test_correspondence_cells_and_icons_are_centered_and_update_on_model_change(qtbot):
    dialog = make_dialog(qtbot)
    page = dialog.controllers_page
    table = page.table
    assert table.item(0, 0).text() == "SOUTH"
    assert table.item(0, 2).text() == "b4"
    assert all(table.item(row, column).textAlignment() == Qt.AlignmentFlag.AlignCenter
               for row in range(table.rowCount()) for column in range(3))
    assert table.item(0, 1).text() == ""
    # Icons are painted by a delegate, not cell widgets that Qt misplaces off-screen.
    assert table.cellWidget(0, 1) is None
    assert isinstance(table.itemDelegateForColumn(1), PromptDelegate)
    assert QSvgRenderer(table.item(0, 1).data(PROMPT_ROLE)).isValid()
    assert "shared-A-Color.svg" in table.item(0, 1).data(SOURCES_ROLE)[0]
    page.model.setCurrentIndex(page.model.findData("sony.dualsense"))
    qtbot.wait(20)
    assert "ps-Cross-Color.svg" in table.item(0, 1).data(SOURCES_ROLE)[0]
    assert page.metadata.field(1).text() == "DualSense"
    assert page.metadata.field(3).text() == "a"*32
    assert page.settings.controller_mappings["device"] == {"SOUTH": "b4"}


def test_all_named_models_have_packaged_svg_illustrations(qapp):
    models = [model for model in load_builtin_catalog() if not model.id.startswith("generic.")]
    assert len(models) == 18
    # Asset-pack silhouettes where the pack has the controller, original drawings otherwise.
    original = {"microsoft.adaptive", "logitech.f310", "logitech.f510", "logitech.f710"}
    for model in models:
        path = ASSET_DIR / model.svg
        assert path.parent.name == ("models" if model.id in original else "library")
        assert path.is_file() and QSvgRenderer(str(path)).isValid()
        assert resolve_artwork(model) == path
        assert not model.verified


def test_custom_illustration_overrides_model_and_missing_custom_falls_back(qapp, tmp_path):
    model = next(model for model in load_builtin_catalog() if model.id == "microsoft.xbox-360")
    custom = tmp_path / "custom.svg"
    custom.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><circle cx="5" cy="5" r="4"/></svg>')
    assert resolve_artwork(model, str(custom)) == custom
    assert resolve_artwork(model, str(tmp_path / "missing.svg")) == ASSET_DIR / model.svg


def test_axes_have_distinct_vector_icons_and_correspondence_controls_survive_scroll(qtbot):
    dialog = make_dialog(qtbot)
    page = dialog.controllers_page
    model = next(model for model in load_builtin_catalog() if model.id == "microsoft.xbox-360")
    paths = {prompt_path(logical, model) for logical in ("LEFT_X", "LEFT_Y", "RIGHT_X", "RIGHT_Y")}
    assert len(paths) == 4 and all(path.is_file() for path in paths)
    page.findChild(QScrollArea, "controllersScroll").verticalScrollBar().setValue(10000)
    page.table.verticalScrollBar().setValue(page.table.verticalScrollBar().maximum())
    qtbot.wait(20)
    row = next(row for row in range(page.table.rowCount()) if page.table.item(row, 0).text() == "LEFT_X")
    assert QSvgRenderer(page.table.item(row, 1).data(PROMPT_ROLE)).isValid()
    assert "input-icons" in page.table.item(row, 1).data(SOURCES_ROLE)[0]
    # Nothing is drawn outside the table: no stray cell widgets.
    assert not page.table.findChildren(SvgView)


def test_custom_models_fall_back_to_their_family_silhouette(qapp):
    from dataclasses import replace
    model = next(model for model in load_builtin_catalog() if model.id == "sony.dualshock-4")
    copy = replace(model, id="custom.copy", svg="")
    assert resolve_artwork(copy) == ASSET_DIR / "library" / "dualsense.svg"


def test_profiles_tab_shows_the_controller_whose_buttons_are_drawn(qtbot):
    from pawz.core.models import Settings
    from pawz.ui.windows import SettingsDialog
    dialog = SettingsDialog(Settings.defaults())
    qtbot.addWidget(dialog)
    preview = dialog.display_model_preview
    assert preview.renderer.isValid()
    picker = dialog.display_model_picker
    picker.setCurrentIndex(picker.findData("nintendo.switch-pro"))
    assert preview.toolTip() == "Nintendo Switch Pro Controller"
    assert preview.renderer.isValid()


def test_models_are_recognized_from_sdl_guid_usb_ids_then_name_fragments():
    from pawz.core.controller_services import GENERIC_MODEL, resolve_model, usb_id
    catalog = load_builtin_catalog()
    switch_pro = "030056fb7e0500000920000000006803"  # a real Switch Pro over Bluetooth
    assert usb_id(switch_pro) == "057e:2009"
    assert usb_id("78696e70757401000000000000000000") is None  # "xinput": no USB ids
    assert usb_id("not hex") is None
    assert resolve_model(catalog, switch_pro, "Wireless Gamepad") == "nintendo.switch-pro"
    assert resolve_model(catalog, "030000005e040000120b000000000000", "") == "microsoft.xbox-series"
    assert resolve_model(catalog, "", "Xbox 360 Controller") == "microsoft.xbox-360"
    assert resolve_model(catalog, "", "PS5 Controller") == "sony.dualsense"
    assert resolve_model(catalog, "", "Nintendo Switch Joy-Con (R)") == "nintendo.joycon"
    assert resolve_model(catalog, "", "XInput Controller") == GENERIC_MODEL
    # The user's choice still wins.
    assert resolve_model(catalog, switch_pro, "", "sony.dualsense") == "sony.dualsense"


def test_pickers_are_titled_and_calibrate_sits_above_the_illustration_buttons(qtbot):
    from PySide6.QtWidgets import QLabel, QPushButton
    dialog = make_dialog(qtbot)
    page = dialog.controllers_page
    buddies = {label.buddy(): label.text() for label in page.findChildren(QLabel) if label.buddy()}
    assert buddies[page.device] == "Known controller" and buddies[page.model] == "Model used"
    calibrate = page.findChild(QPushButton, "calibrateController")
    buttons = [page.findChild(QPushButton, name)
               for name in ("changeIllustration", "importIllustration", "restoreIllustration")]
    assert [button.text() for button in buttons] == ["Change illustration…", "Import custom…", "Restore default"]
    cell = page.metadata.cellWidget(0, 0)
    assert all(cell.isAncestorOf(widget) for widget in (calibrate, *buttons, page.artwork))
    def top(widget): return widget.mapTo(cell, widget.rect().topLeft()).y()
    assert top(page.artwork) < top(calibrate) < top(buttons[0])
    assert len({top(button) for button in buttons}) == 1  # one row


def test_illustration_dialog_lists_bundled_artwork_and_previews_the_selection(qtbot):
    from pawz.ui.controllers_page import IllustrationDialog
    catalog = load_builtin_catalog()
    from pawz.core.controller_catalog import ControllerCatalog
    full = ControllerCatalog(ASSET_DIR / "missing-custom.json")
    model = next(model for model in catalog if model.id == "nintendo.switch-pro")
    dialog = IllustrationDialog(full, model, "asset:library/dualsense.svg")
    qtbot.addWidget(dialog)
    references = [dialog.choices.item(row).data(Qt.ItemDataRole.UserRole)
                  for row in range(dialog.choices.count())]
    assert references[0] is None  # the model's default
    assert "asset:library/switch-pro.svg" in references and "asset:models/logitech.f310.svg" in references
    assert dialog.selection == "asset:library/dualsense.svg"
    assert dialog.choices.currentItem().text() == "DualSense"
    assert dialog.preview.renderer.isValid()
    dialog.choices.setCurrentRow(0)
    assert dialog.selection is None and dialog.preview.renderer.isValid()


def test_asset_references_stay_inside_the_artwork_folders():
    from pawz.ui.controller_assets import bundled_artwork
    assert bundled_artwork("library/switch-pro.svg") == ASSET_DIR / "library" / "switch-pro.svg"
    assert bundled_artwork("xbox.svg") == ASSET_DIR / "xbox.svg"
    assert bundled_artwork("../../../secret.svg") == ASSET_DIR / "secret.svg"
    assert bundled_artwork("prompts/Shared/x.svg") == ASSET_DIR / "x.svg"


def test_guid_can_be_copied(qtbot):
    from PySide6.QtWidgets import QApplication
    dialog = make_dialog(qtbot)
    page = dialog.controllers_page
    assert page.metadata.field(3).text() == "a" * 32
    assert not page.metadata.copy_guid.icon().isNull()
    page.metadata.copy_guid.click()
    assert QApplication.clipboard().text() == "a" * 32


def test_use_model_button_reflects_the_model_in_use(qtbot):
    dialog = make_dialog(qtbot)
    page = dialog.controllers_page
    button = page.apply_model
    assert page.model.currentData() == page.used_model() == "microsoft.xbox-360"
    assert not button.isEnabled() and button.text().startswith("✓")
    assert abs(button.width() - page.metadata.width()) <= 1  # as wide as the table
    page.model.setCurrentIndex(page.model.findData("sony.dualsense"))
    assert button.isEnabled() and button.text() == "Use this model for this controller"
    button.click()
    assert page.used_model() == "sony.dualsense" and not button.isEnabled()


def test_rename_shortcut_fills_and_selects_the_custom_name(qtbot):
    from PySide6.QtWidgets import QPushButton
    dialog = make_dialog(qtbot)
    page = dialog.controllers_page
    assert page.name.text() == "" and page.name.placeholderText() == "Xbox 360"
    page.findChild(QPushButton, "renameController").click()
    assert page.name.text() == "Xbox 360" and page.name.selectedText() == "Xbox 360"
    page.name.setText("Xbox 360")
    page.rename()  # the default name is not stored as a custom one
    assert "name" not in page.preferences()
    page.name.setText("Living room pad")
    page.rename()
    assert page.preferences()["name"] == "Living room pad"


def test_tables_stand_alone_and_the_scroll_bar_skips_the_header(qtbot):
    from PySide6.QtWidgets import QFrame
    dialog = make_dialog(qtbot)
    page = dialog.controllers_page
    assert not page.findChildren(QFrame, "tableFrame")
    spacer = page.table.findChild(QWidget, "scrollHeaderSpacer")
    assert spacer is not None
    assert spacer.height() == page.table.horizontalHeader().height()


def test_copy_icon_turns_into_a_tick_for_a_moment(qtbot):
    from pawz.ui import controller_tables
    dialog = make_dialog(qtbot)
    table = dialog.controllers_page.metadata
    copy_icon = table.copy_guid.icon().cacheKey()
    table.copy_guid.click()
    assert table.copy_guid.toolTip() == "Copied" and table.copy_guid.icon().cacheKey() != copy_icon
    assert 2000 <= controller_tables.COPIED_FEEDBACK_MS <= 3000
    table._copied_timer.setInterval(10)
    table._copied_timer.start()
    qtbot.waitUntil(lambda: table.copy_guid.toolTip() == "Copy", timeout=1000)


def test_illustration_dialog_import_button_matches_the_list(qtbot):
    from PySide6.QtWidgets import QPushButton

    from pawz.core.controller_catalog import ControllerCatalog
    from pawz.ui.controllers_page import IllustrationDialog
    model = next(model for model in load_builtin_catalog() if model.id == "nintendo.switch-pro")
    dialog = IllustrationDialog(ControllerCatalog(ASSET_DIR / "missing-custom.json"), model, None)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.wait(20)
    button = dialog.findChild(QPushButton, "importIllustration")
    assert abs(button.width() - dialog.choices.width()) <= 1
    assert dialog.preview.render_scale == 0.75


def test_credits_name_the_asset_pack_author(qtbot):
    from PySide6.QtWidgets import QLabel
    dialog = make_dialog(qtbot)
    credits = dialog.findChild(QLabel, "credits")
    assert "AL2009man" in credits.text() and "Gamepad Asset Pack" in credits.text()
    assert credits.openExternalLinks()
