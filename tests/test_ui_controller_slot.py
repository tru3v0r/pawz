import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QToolTip,
    QWidget,
)

import pawz.main as app_main
from pawz.core.models import Profile, Settings
from pawz.ui.controller_assets import SvgView
from pawz.ui.windows import (
    CSS,
    ControllerSlot,
    DebugWindow,
    MainWindow,
    ProfileCreationDialog,
    ProfileDialog,
    ProfileSectionFrame,
    ProfileSectionHeading,
    SettingsDialog,
    load_fonts,
)


def test_controller_slot_marks_primary_and_requests_transfer():
    QApplication.instance() or QApplication([])
    load_fonts()
    slot = ControllerSlot()
    requested = []
    slot.set_primary_requested.connect(requested.append)

    slot.configure("guid#1", "Controller 2", True, "medium", ["Default"], "Default", False, 2)

    assert slot.artwork.primary is False
    assert not slot.set_primary.isHidden()
    assert slot.battery.text() == "~60%"
    assert slot.profile_picker.currentData() == "Default"
    assert [slot.profile_picker.itemText(i)
            for i in range(slot.profile_picker.count())] == ["Default"]
    slot.set_primary.click()
    assert requested == ["guid#1"]

    slot.configure("guid#1", "Controller 2", True, "full", ["Default"], "Default", True, 2)

    assert slot.artwork.primary is True
    assert slot.set_primary.isHidden()


def test_controller_battery_animates_from_empty_through_percentage_colors():
    QApplication.instance() or QApplication([])
    slot = ControllerSlot()

    slot.configure("guid#1", "Controller", True, "full", ["Default"], None, True, 1)

    assert slot.battery_bar.value() == 0
    assert slot.battery_animation.state().name == "Running"
    slot.battery_animation.setCurrentTime(slot.battery_animation.duration() // 2)
    assert slot.battery_bar.value() == 50
    assert "#ffc21c" in slot.battery_bar.styleSheet()
    slot.battery_animation.setCurrentTime(slot.battery_animation.duration())
    assert slot.battery_bar.value() == 100
    assert "#00c96b" in slot.battery_bar.styleSheet()


def test_controller_battery_only_animates_when_connection_starts():
    QApplication.instance() or QApplication([])
    slot = ControllerSlot()

    slot.configure("guid#1", "Controller", True, "low", ["Default"], None, True, 1)
    slot.battery_animation.setCurrentTime(slot.battery_animation.duration())
    slot.configure("guid#1", "Controller", True, "medium", ["Default"], None, True, 1)

    assert slot.battery_bar.value() == 60
    assert slot.battery_animation.state().name == "Stopped"


def test_controller_battery_animates_when_level_arrives_after_connect():
    QApplication.instance() or QApplication([])
    slot = ControllerSlot()

    slot.configure("guid#1", "Controller", True, "unknown", ["Default"], None, True, 1)
    slot.update_battery("full")

    assert slot.battery_bar.value() == 0
    assert slot.battery_animation.state().name == "Running"
    slot.battery_animation.setCurrentTime(slot.battery_animation.duration() // 2)
    assert slot.battery_bar.value() == 50
    assert "#ffc21c" in slot.battery_bar.styleSheet()


def test_inter_font_is_loaded_from_assets():
    QApplication.instance() or QApplication([])
    load_fonts()

    from PySide6.QtGui import QFont, QFontInfo

    assert QFontInfo(QFont("Inter 18pt", 12)).exactMatch()


def test_profile_dialog_exposes_magnet_strength_slider():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(CSS)
    dialog = ProfileDialog(Settings.defaults().profiles["Default"])
    slider = dialog.findChild(QSlider, "magnetStrength")

    assert slider is not None
    assert slider.value() == 50
    slider.setValue(72)
    assert dialog.profile.magnet_strength == 72


def test_profile_dialog_scroll_area_keeps_dark_theme_without_white_background():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(CSS)
    dialog = ProfileDialog(Settings.defaults().profiles["Default"])
    dialog.show()
    app.processEvents()

    viewport = dialog.findChild(QScrollArea, "profileScroll")
    assert viewport is not None
    image = dialog.grab().toImage()
    point = viewport.viewport().mapTo(
        dialog, QPoint(3, 3))

    assert image.pixelColor(point) == QColor("#223d68")
    dialog.close()


def test_application_section_header_overlays_frame_border_with_remove_button():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(CSS)
    profile = Settings.defaults().profiles["Default"]
    dialog = ProfileDialog(profile)
    editor = dialog.editor
    section = next(
        section for section in editor.findChildren(ProfileSectionFrame, "profileSectionFrame")
        if section.findChild(QLabel, "profileSectionTitle").text() == "Firefox")
    assert section is not None
    dialog.resize(790, 680)
    dialog.show()
    app.processEvents()
    editor.findChild(QScrollArea, "profileScroll").verticalScrollBar().setValue(section.y())
    app.processEvents()

    header = section.findChild(QWidget, "profileSectionHeader")
    title = section.findChild(QLabel, "profileSectionTitle")
    remove = section.findChild(QPushButton, "removeSection")
    icon = section.findChild(QLabel, "profileSectionIcon")
    rule = header.findChild(QFrame, "profileSectionRule")
    border = section.findChild(QFrame, "profileSectionBorder")

    assert header is not None
    assert title is not None
    assert remove is not None
    assert icon is not None
    assert rule is not None
    assert border is not None
    assert section.height() > 0
    assert header.y() + header.height() // 2 == section.HEADER_OVERLAP
    assert title.parentWidget() is header
    assert remove.parentWidget() is header
    assert icon.x() == 18
    assert title.x() == icon.geometry().right() + 1
    assert rule.width() == border.width()
    assert remove.geometry().center().y() == rule.y()
    assert remove.accessibleName() == "Supprimer"
    assert remove.size().toTuple() == (21, 21)
    assert remove.iconSize().toTuple() == (16, 16)
    assert abs(remove.geometry().center().x() - border.width()) <= 1
    assert "QPushButton#removeSection { color:#ffffff; background:#20527b" in CSS
    image = dialog.grab().toImage()
    assert image.pixelColor(title.mapTo(dialog, QPoint(0, header.height() // 2))) == QColor("#1b355b")
    assert icon.size().toTuple() == (16, 22)
    assert image.pixelColor(icon.mapTo(dialog, QPoint(0, 0))) == QColor("#1b355b")
    assert not remove.icon().isNull()
    remove_image = remove.grab().toImage()
    assert remove_image.pixelColor(
        remove_image.width() // 2, remove_image.height() // 2).red() > 220
    assert image.pixelColor(remove.mapTo(
        dialog, QPoint(3, remove.height() // 2))) == QColor("#20527b")
    hotkey = section.findChild(SvgView, "bindingPrompt")
    remove_binding = section.findChild(QPushButton, "removeBinding")
    add_shortcut = section.findChild(QPushButton, "settingsAction")
    assert hotkey is not None and remove_binding is not None and add_shortcut is not None
    actions = section.findChild(QFrame, "profileSectionActions")
    separator = section.findChild(QFrame, "profileSectionActionsSeparator")
    assert actions is not None and separator is not None
    assert actions.parentWidget() is border
    assert separator.width() == actions.width()
    assert separator.mapTo(actions, QPoint(0, 0)).x() == 0
    content = section.findChild(QWidget, "profileSectionContent")
    assert content is not None
    assert content.geometry().bottom() < actions.geometry().top()
    assert actions.geometry().bottom() == border.rect().bottom() - 1
    assert add_shortcut.mapTo(actions, QPoint(
        add_shortcut.width() // 2, add_shortcut.height() // 2)).x() == actions.width() // 2
    actions_image = actions.grab().toImage()
    assert actions_image.pixelColor(
        actions.width() // 2, actions.height() - 3) == QColor("#17345e")
    assert actions_image.pixelColor(
        separator.width() // 2, separator.height() // 2) == QColor("#4b83bd")
    for button in (add_shortcut,):
        assert image.pixelColor(button.mapTo(
            dialog, QPoint(3, button.height() // 2))) == QColor("#20527b")
    heading = next(
        heading for heading in editor.findChildren(ProfileSectionHeading)
        if heading.label.text() == "SENSIBILITÉ")
    assert heading.rule.width() > 0
    assert heading.rule.x() >= heading.label.geometry().right() + 8
    editor.findChild(QScrollArea, "profileScroll").verticalScrollBar().setValue(0)
    app.processEvents()
    heading_image = heading.grab().toImage()
    assert heading_image.pixelColor(
        heading.rule.x(), heading.rule.y()) == QColor("#4b83bd")
    assert all(button.size().toTuple() == (24, 24)
               for button in editor.findChildren(QPushButton, "removeBinding"))
    for section in editor.findChildren(ProfileSectionFrame, "profileSectionFrame"):
        section_remove = section.findChild(QPushButton, "removeSection")
        if section_remove is not None:
            section_header = section.findChild(QWidget, "profileSectionHeader")
            section_rule = section_header.findChild(QFrame, "profileSectionRule")
            assert section_remove.geometry().center().y() == section_rule.y()
    heading_index = editor.sections.indexOf(heading)
    assert editor.sections.itemAt(heading_index - 1).spacerItem().sizeHint().height() == 16


def test_profile_sections_navigation_order_and_visual_controls():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(CSS)
    dialog = ProfileDialog(Settings.defaults().profiles["Default"])
    dialog.resize(790, 680)
    dialog.show()
    app.processEvents()
    editor = dialog.editor

    headings = [heading.label.text() for heading in editor.findChildren(ProfileSectionHeading)]
    assert headings[:4] == ["SENSIBILITÉ", "NAVIGATION", "APPLICATIONS", "SITES WEB"]
    for heading in editor.findChildren(ProfileSectionHeading):
        layout_index = editor.sections.indexOf(heading)
        assert layout_index > 0
        spacer = editor.sections.itemAt(layout_index - 1).spacerItem()
        assert spacer is not None and spacer.sizeHint().height() >= 8

    youtube = next(
        section for section in editor.findChildren(ProfileSectionFrame, "profileSectionFrame")
        if section.findChild(QLabel, "profileSectionTitle").text() == "youtube.com")
    youtube_icon = youtube.findChild(QLabel, "profileSectionIcon")
    assert youtube_icon is not None
    assert not youtube_icon.icon.isNull()

    application = next(
        section for section in editor.findChildren(ProfileSectionFrame, "profileSectionFrame")
        if section.findChild(QLabel, "profileSectionTitle").text() == "Firefox")
    content = application.findChild(QWidget, "profileSectionContent")
    hotkey = application.findChild(SvgView, "bindingPrompt")
    remove = application.findChild(QPushButton, "removeBinding")
    assert content is not None and hotkey is not None and remove is not None
    assert hotkey.width() == 72
    assert hotkey.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    for button in application.findChildren(SvgView, "bindingPrompt"):
        assert button.width() >= button.height()
        assert button.renderer.isValid()
    assert remove.size().toTuple() == (24, 24)
    assert remove.iconSize().toTuple() == (14, 14)
    remove_image = remove.grab().toImage()
    assert remove_image.pixelColor(
        remove_image.width() // 2, remove_image.height() // 2).red() > 220

    mouse_label = editor.findChild(QLabel, "mouseSpeedLabel")
    mouse_control = editor.findChild(QWidget, "mouseSensitivityControl")
    magnet_label = editor.findChild(QLabel, "magnetLabel")
    magnet_control = editor.findChild(QWidget, "magnetControl")
    auto = editor.findChild(QCheckBox, "magnetAuto")
    mouse_slider = editor.findChild(QSlider, "mouse_speed")
    magnet_slider = editor.findChild(QSlider, "magnetStrength")
    scroll_slider = editor.findChild(QSlider, "scroll_speed")
    deadzone_slider = editor.findChild(QSlider, "deadzone")
    assert mouse_label is not None and mouse_control is not None
    assert magnet_label is not None and magnet_label.text() == "Magnétisme"
    assert magnet_control is not None and auto is not None and auto.text() == "Automatique"
    assert mouse_slider is not None and magnet_slider is not None
    assert scroll_slider is not None and deadzone_slider is not None
    assert editor.findChild(QCheckBox, "magnetEnabled") is None
    assert magnet_slider.parentWidget().parentWidget() is magnet_control
    # Its own row, between Souris and Molette, the options under the slider.
    assert magnet_control.mapTo(editor, QPoint(0, 0)).y() > (
        mouse_control.mapTo(editor, QPoint(0, mouse_control.height())).y())
    assert scroll_slider.mapTo(editor, QPoint(0, 0)).y() > (
        magnet_control.mapTo(editor, QPoint(0, magnet_control.height())).y())
    assert auto.mapTo(magnet_control, QPoint(0, 0)).y() > (
        magnet_slider.mapTo(magnet_control, QPoint(0, magnet_slider.height())).y())
    assert mouse_slider.mapTo(editor, QPoint(0, 0)).x() > mouse_label.mapTo(
        editor, QPoint(mouse_label.width(), 0)).x()
    assert deadzone_slider.mapTo(editor, QPoint(0, 0)).y() - (
        scroll_slider.mapTo(editor, QPoint(0, 0)).y()) >= 20
    assert "QWidget#profileEditor QSlider::groove:horizontal" in CSS
    assert "QWidget#profileEditor QSlider::groove:horizontal { height:4px; background:#10233f" in CSS
    assert "QWidget#profileEditor QSlider::add-page:horizontal { background:#10233f" in CSS
    slider_image = mouse_slider.grab().toImage()
    assert slider_image.pixelColor(10, 0) == QColor("#1b355b")
    navigation = next(
        section for section in editor.findChildren(ProfileSectionFrame, "profileSectionFrame")
        if section.findChild(QLabel, "profileSectionTitle").text() == "Général")
    assert navigation.findChild(QFrame, "profileSectionBorder") is not None
    assert navigation.findChild(QFrame, "profileSectionActionsSeparator") is not None
    assert all(section.findChild(QFrame, "profileSectionActionsSeparator") is not None
               for section in editor.findChildren(ProfileSectionFrame, "profileSectionFrame"))

    settings_dialog = SettingsDialog(Settings.defaults())
    settings_dialog.resize(708, 720)
    settings_dialog.show()
    app.processEvents()
    general_headings = settings_dialog.tabs.widget(0).findChildren(ProfileSectionHeading)
    assert [heading.label.text() for heading in general_headings] == [
        "DÉMARRAGE", "PROFILS", "MODE JEU", "DEBUG"]
    assert not settings_dialog.findChildren(QFrame, "generalSection")
    assert not settings_dialog.findChildren(QGroupBox)
    for heading in general_headings:
        assert heading.rule.x() >= heading.label.geometry().right() + 8
        heading_image = heading.grab().toImage()
        line_color = heading_image.pixelColor(heading.rule.x(), heading.rule.y())
        assert line_color == QColor("#4b83bd")
    debug_startup = settings_dialog.findChild(QCheckBox, "debugWindowOnStartup")
    assert debug_startup is settings_dialog.debug_startup_checkbox
    assert debug_startup.text() == "Lancer la fenêtre de debug au démarrage"
    assert not debug_startup.isChecked()
    debug_button = settings_dialog.findChild(QPushButton, "openDebugWindow")
    assert debug_button is settings_dialog.debug_button
    debug_button_image = debug_button.grab().toImage()
    assert debug_button_image.pixelColor(
        debug_button_image.width() // 2, 0) == QColor("#3187c7")
    assert "QPushButton#openDebugWindow" in app.styleSheet()
    assert "QTabWidget#settingsTabs QTabBar::tab:selected" in CSS
    assert "font-weight:bold" in CSS
    profile_label = next(
        label for label in settings_dialog.tabs.widget(0).findChildren(QLabel)
        if label.text() == "Profil assigné par défaut")
    assert settings_dialog.default_profile_picker.mapTo(
        settings_dialog, QPoint(0, 0)).x() - profile_label.mapTo(
            settings_dialog, QPoint(profile_label.width(), 0)).x() >= 8
    settings_dialog.close()
    dialog.close()


def test_section_and_control_spacing_matches_across_settings_tabs():
    app = QApplication.instance() or QApplication([])
    load_fonts()
    app.setStyleSheet(CSS)
    section_gap = 18
    row_gap = 12

    profile_dialog = ProfileDialog(Settings.defaults().profiles["Default"])
    profile_dialog.resize(790, 680)
    profile_dialog.show()
    app.processEvents()
    editor = profile_dialog.editor
    headings = editor.findChildren(ProfileSectionHeading)
    for heading in headings:
        heading_index = editor.sections.indexOf(heading)
        first_widget = next(
            item.widget() for index in range(heading_index + 1, editor.sections.count())
            if (item := editor.sections.itemAt(index)).widget() is not None)
        assert first_widget.y() - heading.geometry().bottom() - 1 == section_gap
        image = heading.grab().toImage()
        assert image.pixelColor(heading.rule.x(), heading.rule.y()) == QColor("#4b83bd")

    sensitivity_heading = next(
        heading for heading in headings if heading.label.text() == "SENSIBILITÉ")
    sensitivity_index = editor.sections.indexOf(sensitivity_heading)
    sensitivity = next(
        editor.sections.itemAt(index).widget()
        for index in range(sensitivity_index + 1, editor.sections.count())
        if editor.sections.itemAt(index).widget() is not None)
    form = sensitivity.layout()
    scroll_row = form.itemAt(0, QFormLayout.ItemRole.FieldRole).geometry()
    wheel_row = form.itemAt(1, QFormLayout.ItemRole.FieldRole).geometry()
    deadzone_row = form.itemAt(2, QFormLayout.ItemRole.FieldRole).geometry()
    assert wheel_row.y() - scroll_row.y() - scroll_row.height() == row_gap
    assert deadzone_row.y() - wheel_row.y() - wheel_row.height() == row_gap

    for section in editor.findChildren(ProfileSectionFrame, "profileSectionFrame"):
        content = section.findChild(QWidget, "profileSectionContent")
        layout = content.layout()
        margins = layout.contentsMargins()
        assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (
            24, section_gap, 24, section_gap)
        assert layout.spacing() == 6
        first_row = layout.itemAt(0).geometry()
        last_row = layout.itemAt(layout.count() - 1).geometry()
        assert first_row.y() == section_gap
        assert content.height() - last_row.y() - last_row.height() == section_gap
    profile_dialog.close()

    settings_dialog = SettingsDialog(Settings.defaults())
    settings_dialog.resize(708, 720)
    settings_dialog.show()
    settings_dialog.startup_checkbox.setChecked(True)
    app.processEvents()
    general = settings_dialog.tabs.widget(0)
    general_layout = general.layout()
    for heading in general.findChildren(ProfileSectionHeading):
        heading_index = general_layout.indexOf(heading)
        first_item = next(
            general_layout.itemAt(index)
            for index in range(heading_index + 1, general_layout.count())
            if general_layout.itemAt(index).widget() is not None
            or general_layout.itemAt(index).layout() is not None)
        assert first_item.geometry().y() - heading.geometry().bottom() - 1 == section_gap
        image = heading.grab().toImage()
        assert image.pixelColor(heading.rule.x(), heading.rule.y()) == QColor("#4b83bd")

    minimized_option = settings_dialog.findChild(QWidget, "minimizedOption")
    minimized_checkbox = settings_dialog.minimized_checkbox
    assert minimized_option.isVisible()
    minimized_top = minimized_checkbox.mapTo(general, QPoint(0, 0)).y()
    startup_bottom = settings_dialog.startup_checkbox.mapTo(
        general, QPoint(0, 0)).y() + settings_dialog.startup_checkbox.height()
    assert minimized_top - startup_bottom == row_gap
    debug_checkbox = settings_dialog.debug_startup_checkbox
    assert settings_dialog.debug_button.y() - debug_checkbox.y() - debug_checkbox.height() == row_gap
    settings_dialog.close()


def test_settings_active_tab_overlaps_panel_border():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(CSS)
    dialog = SettingsDialog(Settings.defaults())
    dialog.resize(780, 700)
    dialog.show()
    app.processEvents()

    pane = dialog.tabs.widget(0).parentWidget()
    assert "QTabWidget#settingsTabs::pane" in CSS
    assert "border-top-left-radius:0px" in CSS
    assert "QTabWidget#settingsTabs::pane { background:#1b355b; border:1px solid #4b83bd" in CSS
    assert "QTabWidget#settingsTabs QTabBar::tab { color:#f5f7fb; background:#1b355b; border:1px solid #4b83bd" in CSS
    assert "QWidget#settingsPage { background:transparent; border:0; }" in CSS
    tab_bar = dialog.tabs.tabBar()
    pane_top = pane.mapTo(dialog, QPoint(0, 0)).y()
    for selected_index in range(dialog.tabs.count()):
        dialog.tabs.setCurrentIndex(selected_index)
        app.processEvents()
        image = dialog.grab().toImage()
        selected_tab = tab_bar.tabRect(selected_index)
        selected_x = tab_bar.mapTo(
            dialog, QPoint(selected_tab.left() + selected_tab.width() // 2, 0)).x()
        inactive_tab = tab_bar.tabRect((selected_index + 1) % dialog.tabs.count())
        inactive_x = tab_bar.mapTo(
            dialog, QPoint(inactive_tab.left() + inactive_tab.width() // 2, 0)).x()
        assert image.pixelColor(selected_x, pane_top) == QColor("#1b355b")
        inactive_bottom = tab_bar.mapTo(
            dialog, QPoint(0, inactive_tab.bottom())).y()
        assert image.pixelColor(inactive_x, inactive_bottom) == QColor("#4b83bd")
        assert image.pixelColor(selected_x, tab_bar.mapTo(
            dialog, QPoint(0, selected_tab.bottom())).y()) == QColor("#1b355b")
        seam = dialog.tabs.findChild(QWidget, "activeTabSeam")
        assert seam is not None
        assert seam.geometry().height() == 1
        assert seam.geometry().x() == tab_bar.x() + selected_tab.x()
        assert seam.geometry().y() == pane.mapTo(dialog.tabs, QPoint(0, 0)).y()
        tab_pane_left = dialog.tabs.mapTo(dialog, QPoint(0, 0)).x()
        assert image.pixelColor(tab_pane_left, pane_top + 1) == QColor("#4b83bd")

    footer = dialog.findChild(QWidget, "settingsFooterActions")
    assert footer is not None
    footer_layout = footer.layout()
    assert footer_layout is not None
    margins = footer_layout.contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (18, 12, 18, 12)
    tab_bottom = dialog.tabs.mapTo(dialog, QPoint(0, dialog.tabs.height())).y()
    save_top = dialog.save_button.mapTo(dialog, QPoint(0, 0)).y()
    assert save_top - tab_bottom >= 12
    dialog.close()


def test_add_profile_separator_is_below_button():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(CSS)
    dialog = SettingsDialog(Settings.defaults(), initial_tab="Profils")
    dialog.resize(780, 700)
    dialog.show()
    app.processEvents()

    separator = dialog.findChild(QFrame, "addProfileSeparator")
    assert separator is not None
    button = dialog.add_profile_button
    button_top = button.mapTo(dialog, QPoint(0, 0)).y()
    button_bottom = button.mapTo(dialog, QPoint(0, button.height())).y()
    separator_top = separator.mapTo(dialog, QPoint(0, 0)).y()
    profile_actions = dialog.findChild(QWidget, "addProfileSeparator").parentWidget()
    profile_margins = profile_actions.layout().contentsMargins()
    button_bottom = button.mapTo(dialog, QPoint(0, button.height())).y()
    assert button_top - profile_actions.mapTo(dialog, QPoint(0, 0)).y() >= 16
    assert separator_top - button_bottom >= 18
    assert profile_margins.bottom() >= 14
    assert separator.width() >= 600
    image = dialog.grab().toImage()
    assert image.pixelColor(button.mapTo(
        dialog, QPoint(3, button.height() // 2))) == QColor("#20527b")
    profile_picker_top = dialog.profile_picker.mapTo(dialog, QPoint(0, 0)).y()
    assert profile_picker_top - separator.mapTo(dialog, QPoint(0, separator.height())).y() >= 12
    dialog.close()


def test_controller_name_wraps_onto_multiple_lines_when_needed():
    app = QApplication.instance() or QApplication([])
    slot = ControllerSlot()
    slot.name.setText("Nintendo Switch Pro Controller with an extra-long name")
    slot.show()
    app.processEvents()

    assert slot.name.wordWrap()
    assert slot.name.height() > 27
    slot.close()


def test_primary_controller_crown_is_centered_on_controller():
    app = QApplication.instance() or QApplication([])
    slot = ControllerSlot()
    artwork = slot.artwork
    artwork.set_state(True, True)
    artwork.show()
    app.processEvents()
    image = artwork.grab().toImage()
    crown_pixels = [
        (x, y)
        for y in range(20, 39)
        for x in range(image.width())
        if (color := image.pixelColor(x, y)).red() > 200
        and color.green() > 150
        and color.blue() < 120
    ]

    assert crown_pixels
    crown_center = (min(x for x, _ in crown_pixels) + max(x for x, _ in crown_pixels)) / 2
    assert abs(crown_center - artwork.width() / 2) <= 1
    crown_bottom = max(
        y for y in range(20, 39)
        for x in range(image.width())
        if (color := image.pixelColor(x, y)).red() > 200
        and color.green() > 150
        and color.blue() < 120
    )
    assert 30 <= crown_bottom <= 42
    artwork.close()


def test_primary_controller_crown_shows_tooltip_on_hover(monkeypatch):
    QApplication.instance() or QApplication([])
    slot = ControllerSlot()
    artwork = slot.artwork
    artwork.set_state(True, True)
    artwork.show()
    show_tooltip = Mock()
    monkeypatch.setattr(QToolTip, "showText", show_tooltip)
    point = QPointF(artwork.width() / 2, 24)
    event = QMouseEvent(
        QEvent.Type.MouseMove, point, point, point,
        Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    artwork.mouseMoveEvent(event)

    assert show_tooltip.call_args.args[1] == "Primary Controller"
    artwork.close()


def test_settings_dialog_separates_general_and_profile_options():
    QApplication.instance() or QApplication([])
    settings = Settings.defaults()
    dialog = SettingsDialog(settings)
    startup = dialog.findChild(QCheckBox, "startupEnabled")
    minimized = dialog.findChild(QCheckBox, "startMinimized")
    default_profile = dialog.findChild(QComboBox, "defaultAssignedProfile")

    assert [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())] == ["GÉNÉRAL", "PROFILS", "MANETTES"]
    assert dialog.width() == 708
    assert dialog.height() == 720
    assert startup is not None
    assert minimized is not None
    assert minimized.parentWidget().isHidden()
    assert default_profile is not None
    assert default_profile.currentText() == "Default"
    startup.setChecked(True)
    assert not minimized.parentWidget().isHidden()
    startup.setChecked(False)
    assert minimized.parentWidget().isHidden()
    assert dialog.profile_editor.findChild(QCheckBox, "startupEnabled") is None


def test_settings_controls_use_dark_theme_for_checks_lists_and_dropdowns():
    QApplication.instance() or QApplication([])
    dialog = SettingsDialog(Settings.defaults())

    assert "checkbox-check.svg" in dialog.styleSheet()
    assert "combo-arrow.svg" in dialog.styleSheet()
    assert "QCheckBox::indicator:checked" in dialog.styleSheet()
    assert "QComboBox::drop-down" in dialog.styleSheet()
    assert "QComboBox#settingsProfilePicker, QComboBox#defaultAssignedProfile" in dialog.styleSheet()
    assert "QComboBox#settingsProfilePicker::drop-down, QComboBox#defaultAssignedProfile::drop-down" in dialog.styleSheet()
    assert "QComboBox#settingsProfilePicker::down-arrow, QComboBox#defaultAssignedProfile::down-arrow" in dialog.styleSheet()
    assert "height:0" in dialog.styleSheet()


def test_shortcut_svg_is_passive_and_pencil_opens_editor(monkeypatch):
    QApplication.instance() or QApplication([])
    dialog = SettingsDialog(Settings.defaults())
    editor = dialog.profile_editor
    prompt = editor.findChild(SvgView, "bindingPrompt")
    assert prompt.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert prompt.focusPolicy() == Qt.FocusPolicy.NoFocus
    opened = []
    def inspect(edit_dialog):
        opened.append(edit_dialog.objectName())
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(QDialog, "exec", inspect)
    editor.findChild(QPushButton, "editBinding").click()
    assert opened == ["bindingEditor"]
    dialog.reject()


def test_closing_settings_keeps_original_preferences():
    QApplication.instance() or QApplication([])
    settings = Settings.defaults()
    dialog = SettingsDialog(settings)
    dialog.settings.display_controller_model = "nintendo.switch-pro"
    dialog.reject()
    assert settings.display_controller_model == "generic.sdl-gamecontroller"


def test_debug_window_has_five_independent_opt_in_event_sources(monkeypatch):
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(CSS)
    window = DebugWindow()
    started = []
    monkeypatch.setattr(
        window.sources, "set_enabled",
        lambda source, enabled: started.append((source, enabled)))

    assert [window.source_buttons[source].text()
            for source, _ in window.SOURCES] == [
                "SetWindowsHookEx", "SetWinEventHook", "UIA", "Raw Input", "ETW"]
    assert all(button.isCheckable() for button in window.source_buttons.values())
    window.source_buttons["set_windows_hook"].click()
    window.source_buttons["set_windows_hook"].click()
    assert started == [
        ("set_windows_hook", True),
        ("set_windows_hook", False),
    ]
    window.append_event("uia", "focus changed")
    assert "[UIA] focus changed" in window.event_list.toPlainText()
    window.close()


def test_settings_general_has_debug_window_button():
    QApplication.instance() or QApplication([])
    dialog = SettingsDialog(Settings.defaults())

    assert dialog.debug_button.text() == "Debug Window"
    assert dialog.findChild(QPushButton, "openDebugWindow") is dialog.debug_button
    dialog.debug_button.click()
    assert dialog.debug_window.isVisible()
    dialog.debug_window.close()


def test_debug_window_does_not_open_automatically(monkeypatch):
    class Signal:
        def connect(self, callback):
            self.callback = callback

    class Application:
        def __init__(self, _argv):
            self.aboutToQuit = Signal()

        def setQuitOnLastWindowClosed(self, _enabled):
            pass

        def setStyleSheet(self, _stylesheet):
            pass

        def exec(self):
            return 0

    bridge = SimpleNamespace(start=Mock(), stop=Mock())
    manager = SimpleNamespace(
        settings_requested=Signal(),
        error=Signal(),
        start=Mock(),
        stop=Mock(),
    )
    window = SimpleNamespace(
        debug_window=SimpleNamespace(close=Mock()),
        show=Mock(),
        showMinimized=Mock(),
        show_debug_window=Mock(),
        show_for_device=Mock(),
        statusBar=Mock(return_value=SimpleNamespace(showMessage=Mock())),
    )
    monkeypatch.setattr(app_main, "os", SimpleNamespace(name="nt", environ={}))
    monkeypatch.setattr(app_main, "sys", SimpleNamespace(argv=["pawz"]))
    monkeypatch.setattr(app_main, "QApplication", Application)
    monkeypatch.setattr(app_main, "load_fonts", Mock())
    monkeypatch.setattr(app_main, "load", Settings.defaults)
    monkeypatch.setattr(app_main, "configure_startup", Mock())
    monkeypatch.setattr(app_main, "BrowserBridge", lambda *_args: bridge)
    monkeypatch.setattr(app_main, "ControllerManager", lambda *_args: manager)
    monkeypatch.setattr(app_main, "MainWindow", lambda *_args: window)

    assert app_main.main() == 0
    window.show.assert_called_once_with()
    window.showMinimized.assert_not_called()
    window.show_debug_window.assert_not_called()
    window.debug_window.close.assert_not_called()


def test_debug_window_opens_at_startup_when_configured(monkeypatch):
    class Signal:
        def connect(self, callback):
            self.callback = callback

    class Application:
        def __init__(self, _argv):
            self.aboutToQuit = Signal()

        def setQuitOnLastWindowClosed(self, _enabled):
            pass

        def setStyleSheet(self, _stylesheet):
            pass

        def exec(self):
            return 0

    settings = Settings.defaults()
    settings.debug_window_on_startup = True
    bridge = SimpleNamespace(start=Mock(), stop=Mock())
    manager = SimpleNamespace(
        settings_requested=Signal(),
        error=Signal(),
        start=Mock(),
        stop=Mock(),
    )
    window = SimpleNamespace(
        debug_window=SimpleNamespace(close=Mock()),
        show=Mock(),
        showMinimized=Mock(),
        show_debug_window=Mock(),
        show_for_device=Mock(),
        statusBar=Mock(return_value=SimpleNamespace(showMessage=Mock())),
    )
    monkeypatch.setattr(app_main, "os", SimpleNamespace(name="nt", environ={}))
    monkeypatch.setattr(app_main, "sys", SimpleNamespace(argv=["pawz"]))
    monkeypatch.setattr(app_main, "QApplication", Application)
    monkeypatch.setattr(app_main, "load_fonts", Mock())
    monkeypatch.setattr(app_main, "load", lambda: settings)
    monkeypatch.setattr(app_main, "configure_startup", Mock())
    monkeypatch.setattr(app_main, "BrowserBridge", lambda *_args: bridge)
    monkeypatch.setattr(app_main, "ControllerManager", lambda *_args: manager)
    monkeypatch.setattr(app_main, "MainWindow", lambda *_args: window)

    assert app_main.main() == 0
    window.show.assert_called_once_with()
    window.show_debug_window.assert_called_once_with()


def test_settings_dialog_edits_each_profile_and_styles_profile_selector():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(CSS)
    settings = Settings.defaults()
    settings.profiles["Other"] = Profile("Other")
    dialog = SettingsDialog(settings)
    selector = dialog.findChild(QComboBox, "settingsProfilePicker")

    assert selector is not None
    assert selector.itemText(0) == "Default"
    assert selector.view().styleSheet() == ""
    assert "QComboBox#settingsProfilePicker, QComboBox#defaultAssignedProfile" in dialog.styleSheet()
    general_selector = dialog.findChild(QComboBox, "defaultAssignedProfile")
    assert general_selector is not None
    for combo in (selector, general_selector):
        assert combo.style().metaObject().className() == "QStyleSheetStyle"
        assert combo.view().styleSheet() == ""
    slider = dialog.profile_editor.findChild(QSlider, "magnetStrength")
    assert slider is not None
    slider.setValue(73)
    selector.setCurrentIndex(1)

    assert dialog.profiles["Default"].magnet_strength == 73
    assert dialog.profile_editor.profile.name == "Other"


def test_settings_profile_selectors_share_themed_dropdown_and_popup():
    app = QApplication.instance() or QApplication([])
    load_fonts()
    app.setStyleSheet(CSS)
    settings = Settings.defaults()
    settings.profiles["Other"] = Profile("Other")
    dialog = SettingsDialog(settings, initial_tab="Profils")
    dialog.resize(708, 720)
    dialog.show()
    app.processEvents()

    selectors = [
        dialog.findChild(QComboBox, "defaultAssignedProfile"),
        dialog.findChild(QComboBox, "settingsProfilePicker"),
    ]
    assert all(selector is not None for selector in selectors)
    dropdown_pixels = []
    for selector in selectors:
        selector.showPopup()
        app.processEvents()
        popup = selector.view()
        assert popup.isVisible()
        palette = popup.palette()
        assert palette.color(palette.ColorRole.Base) == QColor("#1b355b")
        assert palette.color(palette.ColorRole.Highlight) == QColor("#2765cc")
        popup_image = popup.grab().toImage()
        assert popup_image.pixelColor(2, 2) == QColor("#1b355b")
        combo_image = selector.grab().toImage()
        assert combo_image.height() == 34
        dropdown_pixels.append(combo_image.pixelColor(
            combo_image.width() - 18, combo_image.height() // 2))
        assert dropdown_pixels[-1] == QColor("#20527b")
        selector.hidePopup()
        app.processEvents()

    assert dropdown_pixels[0] == dropdown_pixels[1]
    dialog.close()


def test_profile_creation_dialog_has_name_and_model_and_confirms_cancel(monkeypatch):
    app = QApplication.instance() or QApplication([])
    dialog = ProfileCreationDialog(["Default", "Other"])
    dialog.show()
    app.processEvents()
    assert dialog.name_input.objectName() == "newProfileName"
    assert dialog.model_picker.objectName() == "profileModel"
    assert dialog.create_button.text() == "Créer le profil"
    assert dialog.cancel_button.text() == "Annuler"
    assert not dialog.create_button.isEnabled()
    dialog.name_input.setText("Nouveau")
    assert dialog.create_button.isEnabled()
    dialog.name_input.setText("Default")
    assert not dialog.create_button.isEnabled()
    dialog.name_input.setText("Nouveau")

    prompts = []

    def decline_cancel(_parent, _title, text, *_args):
        prompts.append(text)
        return QMessageBox.StandardButton.No

    monkeypatch.setattr("pawz.ui.windows.QMessageBox.question", decline_cancel)
    dialog.cancel_button.click()
    assert dialog.isVisible()
    assert prompts == ["Êtes-vous sûre de vouloir annuler la création du profil en cours ?"]

    monkeypatch.setattr(
        "pawz.ui.windows.QMessageBox.question",
        lambda *_args: QMessageBox.StandardButton.Yes)
    dialog.cancel_button.click()
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_settings_add_profile_copies_selected_model(monkeypatch):
    QApplication.instance() or QApplication([])
    dialog = SettingsDialog(Settings.defaults())

    def accept_creation(creation):
        creation.name_input.setText("Custom")
        creation.model_picker.setCurrentText("Default")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(ProfileCreationDialog, "exec", accept_creation)
    dialog.add_profile()

    assert "Custom" in dialog.profiles
    assert dialog.profile_picker.currentText() == "Custom"
    assert dialog.profile_editor.profile.name == "Custom"
    assert dialog.profile_editor.profile.dump() == dialog.profiles["Default"].dump() | {
        "name": "Custom", "profile_id": dialog.profile_editor.profile.profile_id
    }
    assert dialog.default_profile_picker.findText("Custom") >= 0


def test_settings_save_keeps_active_profile_editor_changes():
    QApplication.instance() or QApplication([])
    dialog = SettingsDialog(Settings.defaults())
    slider = dialog.profile_editor.findChild(QSlider, "magnetStrength")
    assert slider is not None
    slider.setValue(88)
    dialog._accept_settings()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.profiles["Default"].magnet_strength == 88


def test_magnet_options_are_saved():
    QApplication.instance() or QApplication([])
    dialog = SettingsDialog(Settings.defaults())
    editor = dialog.profile_editor
    boxes = {name: editor.findChild(QCheckBox, name)
             for name in ("magnetAuto", "magnetBackground", "magnetHaptics")}
    assert all(box is not None for box in boxes.values())
    assert [box.isChecked() for box in boxes.values()] == [True, False, True]
    for box in boxes.values():
        box.toggle()
    dialog._accept_settings()
    profile = dialog.profiles["Default"]
    assert (profile.magnet_auto, profile.magnet_background, profile.magnet_haptics) == (
        False, True, False)


def test_main_window_lists_known_controllers_and_scrolls_overflow(monkeypatch):
    monkeypatch.setattr("pawz.ui.windows.configure_startup", lambda _settings: None)
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(CSS)
    monkeypatch.setattr("pawz.ui.windows.save", lambda _settings: None)

    settings = Settings.defaults()
    connected_key = "connected#0"
    settings.primary_device = connected_key
    settings.known_devices = {
        connected_key: "Connected controller",
        **{f"known#{index}": f"Known controller {index}" for index in range(6)},
    }

    class Signal:
        def connect(self, _callback):
            pass

    manager = SimpleNamespace(
        controllers={connected_key: SimpleNamespace(name="Connected controller")},
        power_levels={connected_key: "full"},
        devices_changed=Signal(),
        controller_button_event=Signal(),
    )
    window = MainWindow(settings, manager)
    window.show()
    app.processEvents()

    assert window.size().width() == 770
    assert window.height() == 440
    assert "font: 9.1pt" in CSS
    assert "font: 31pt 'Super Water'" in CSS
    brand = window.findChild(QLabel, "brand")
    brand_icon = window.findChild(QLabel, "brandIcon")
    assert brand is not None
    assert brand.font().pointSizeF() == 24.8
    assert brand_icon.width() == 27 and not brand_icon.icon.isNull()
    assert brand_icon.font().pointSizeF() == 13
    assert window.slots[0].artwork.size().toTuple() == (126, 97)
    assert window.slots[0].width() == 140
    assert window.slots[0].name.font().pointSizeF() == 10
    assert window.slots[0].battery.font().pointSizeF() == 9.1
    assert window.slots[0].profile_picker.font().pointSizeF() == 9.1
    assert window.slots[0].forget_button.font().pointSizeF() == 9.1
    assert window.slots[0].set_primary.font().pointSizeF() == 9.1
    footer = window.findChild(QWidget, "bottomButtonBar")
    assert footer is not None
    assert next(button for button in footer.findChildren(QPushButton)
                if button.text() == "Manage profiles").font().pointSizeF() == 11.8
    assert window.findChild(QPushButton, "windowControl").font().pointSizeF() == 22
    assert "border-bottom:0" in CSS
    assert "QPushButton#removeBinding" in CSS
    assert "QPushButton#settingsAction, QPushButton#openDebugWindow {" in CSS
    assert len(window.slots) == len(settings.known_devices)
    assert [slot.name.text() for slot in window.slots] == list(settings.known_devices.values())
    assert window.slots[0].artwork.connected
    assert not window.slots[1].artwork.connected
    assert window.tray.contextMenu().objectName() == "trayMenu"
    assert "#1b355b" in window.tray.contextMenu().styleSheet()
    viewport_corner = window.controller_scroll.viewport().mapTo(
        window, QPoint(window.controller_scroll.viewport().width() - 8,
                       window.controller_scroll.viewport().height() - 8))
    assert window.grab().toImage().pixelColor(viewport_corner).name() == "#223d68"
    assert window.controller_scroll.horizontalScrollBar().maximum() > 0
    assert window.previous_controllers[1].isHidden()
    assert not window.next_controllers[1].isHidden()
    assert footer.height() == 83
    assert next(button for button in footer.findChildren(QPushButton)
                if button.text() == "Manage profiles").size().toTuple() == (196, 36)
    controller_bottom = window.slots[0].mapTo(
        window, QPoint(0, window.slots[0].height())).y()
    footer_top = footer.mapTo(window, QPoint(0, 0)).y()
    assert footer_top - controller_bottom <= 65
    assert window.slots[0].profile_picker.geometry().top() - window.slots[0].battery_bar.geometry().bottom() >= 6

    opened_tabs = []

    def reject_settings(dialog):
        opened_tabs.append(dialog.tabs.tabText(dialog.tabs.currentIndex()))
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(SettingsDialog, "exec", reject_settings)
    manage_button = next(
        button for button in window.findChildren(QPushButton)
        if button.text() == "Manage profiles")
    manage_button.click()
    assert opened_tabs == ["PROFILS"]
    settings_button = next(
        button for button in window.findChildren(QPushButton)
        if button.text() == "Settings")
    settings_button.click()
    assert opened_tabs == ["PROFILS", "GÉNÉRAL"]

    settings.profiles["Alternate"] = Profile("Alternate")

    def save_alternate_default(dialog):
        dialog.default_profile_picker.setCurrentText("Alternate")
        dialog._accept_settings()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(SettingsDialog, "exec", save_alternate_default)
    window.open_settings()
    assert settings.default_profile == "Alternate"
    assert window.slots[0].profile_picker.currentText() == "Alternate"

    window.next_controllers[1].click()
    app.processEvents()
    assert window.controller_scroll.horizontalScrollBar().value() > 0
    assert not window.previous_controllers[1].isHidden()

    scrollbar = window.controller_scroll.horizontalScrollBar()
    while scrollbar.value() < scrollbar.maximum():
        window.next_controllers[1].click()
        app.processEvents()
    assert scrollbar.value() == scrollbar.maximum()
    assert window.next_controllers[1].isHidden()
    while scrollbar.value() > 0:
        window.previous_controllers[1].click()
        app.processEvents()
    assert window.controller_scroll.horizontalScrollBar().value() == 0
    assert window.previous_controllers[1].isHidden()

    window.show_debug_window()
    assert window.debug_window.isVisible()
    window.tray.hide()
    window._battery_timer.stop()
    window.close()
    window.debug_window.close()


def test_disconnected_controller_can_be_forgotten(monkeypatch):
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(CSS)
    monkeypatch.setattr("pawz.ui.windows.save", lambda _settings: None)
    monkeypatch.setattr(
        "pawz.ui.windows.QMessageBox.question",
        lambda *_args: QMessageBox.StandardButton.Yes)
    settings = Settings.defaults()
    settings.known_devices = {
        "connected#0": "Connected controller",
        "ghost#0": "Disconnected controller",
    }
    settings.assignments["ghost#0"] = "Default"

    class Signal:
        def connect(self, _callback):
            pass

    manager = SimpleNamespace(
        controllers={"connected#0": SimpleNamespace(name="Connected controller")},
        power_levels={"connected#0": "full"},
        devices_changed=Signal(),
        controller_button_event=Signal(),
    )
    window = MainWindow(settings, manager)
    window.show()
    app.processEvents()

    connected_slot, disconnected_slot = window.slots
    assert connected_slot.forget_button.isHidden()
    assert not disconnected_slot.forget_button.isHidden()
    assert disconnected_slot.forget_button.width() == 59

    disconnected_slot.forget_button.click()
    app.processEvents()

    assert "ghost#0" not in settings.known_devices
    assert "ghost#0" not in settings.assignments
    assert len(window.slots) == 1

    window.tray.hide()
    window._battery_timer.stop()
    window.close()
    window.debug_window.close()
