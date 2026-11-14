from PySide6.QtCore import Qt
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QScrollArea

from pawz.core.controller_catalog import load_builtin_catalog
from pawz.core.models import Settings
from pawz.ui.controller_assets import ASSET_DIR, SvgView, prompt_path, resolve_artwork
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
    dialog.tabs.setCurrentIndex(2)
    dialog.resize(820, 760)
    dialog.show()
    qtbot.wait(30)
    return dialog


def test_identification_has_real_fields_centered_in_a_centered_table(qtbot):
    dialog = make_dialog(qtbot)
    table = dialog.controllers_page.metadata
    assert table.rowCount() == 5 and table.columnCount() == 2
    assert [table.item(row, 0).text() for row in range(5)] == ["Manufacturer", "Model", "Family", "SDL GUID", "Status"]
    assert [table.item(row, 1).text() for row in range(5)] == ["Microsoft", "Xbox 360", "xbox", "a"*32, "Not verified on hardware"]
    assert all(table.item(row, col).textAlignment() == Qt.AlignmentFlag.AlignCenter
               for row in range(5) for col in range(2))
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
    icon = table.cellWidget(0, 1)
    assert isinstance(icon, SvgView) and icon.renderer.isValid()
    assert icon.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert "shared-A-Color.svg" in icon.property("svgSources")[0]
    page.model.setCurrentIndex(page.model.findData("sony.dualsense"))
    qtbot.wait(20)
    assert "ps-Cross-Color.svg" in table.cellWidget(0, 1).property("svgSources")[0]
    assert page.metadata.item(1, 1).text() == "DualSense"
    assert page.metadata.item(3, 1).text() == "a"*32
    assert page.settings.controller_mappings["device"] == {"SOUTH": "b4"}


def test_all_named_models_have_packaged_original_svg_illustrations(qapp):
    models = [model for model in load_builtin_catalog() if not model.id.startswith("generic.")]
    assert len(models) == 18
    for model in models:
        path = ASSET_DIR / model.svg
        assert path.parent.name == "models"
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
    assert page.table.cellWidget(row, 1).renderer.isValid()
    assert "input-icons" in page.table.cellWidget(row, 1).property("svgSources")[0]
