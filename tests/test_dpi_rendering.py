import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QLabel

from pawz.core.models import Settings
from pawz.ui.rendering import ScalableIconLabel, vector_icon
from pawz.ui.windows import CSS, SettingsDialog, load_fonts


@pytest.mark.parametrize("ratio", [1.0, 1.25, 1.5, 2.0])
@pytest.mark.parametrize("name", ["pencil", "cross", "duplicate", "profiles", "settings", "youtube"])
def test_vector_icons_render_at_requested_device_resolution(qapp, ratio, name):
    icon = vector_icon(name)
    for mode in (QIcon.Mode.Normal, QIcon.Mode.Disabled):
        image = icon.pixmap(QSize(18, 18), ratio, mode)
        assert not image.isNull()
        # The old 20px bitmap engine could not provide native 27/36px images.
        assert image.devicePixelRatio() == ratio
        assert abs(max(image.width(), image.height()) - 18 * ratio) <= 0.5


def test_text_rendering_preferences_survive_stylesheet_polish(qapp, qtbot):
    load_fonts()
    qapp.setStyleSheet(CSS)
    dialog = SettingsDialog(Settings.defaults())
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.wait(20)
    for widget in (dialog.profile_picker, dialog.display_model_picker,
                   dialog.findChild(QLabel, "profilePickerLabel"), dialog.tabs.tabBar()):
        assert widget.font().hintingPreference() == QFont.HintingPreference.PreferVerticalHinting
        assert widget.font().styleStrategy() & QFont.StyleStrategy.PreferAntialias


def test_section_icons_use_dynamic_icon_painting(qapp, qtbot):
    dialog = SettingsDialog(Settings.defaults())
    qtbot.addWidget(dialog)
    labels = dialog.profile_editor.findChildren(ScalableIconLabel, "profileSectionIcon")
    assert labels
    assert all(not label.icon.isNull() and label.pixmap().isNull() for label in labels)
