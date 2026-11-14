"""Modern Qt configuration window with profile and context editors."""
from __future__ import annotations

import copy
import ctypes
import os
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QLocale, QPoint, QProcess, QPropertyAnimation, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFontDatabase,
    QIcon,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLayout,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSystemTrayIcon,
    QTabWidget,
    QTextEdit,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from pawz import APP_NAME
from pawz.core.controller_catalog import ControllerCatalog
from pawz.core.controller_services import resolve_model
from pawz.core.controllers import battery_percentage
from pawz.core.models import (
    ACTIONS,
    BUTTONS,
    SYSTEM_DEFAULT_PROFILE_ID,
    Binding,
    Profile,
    normalize_trigger,
)
from pawz.engine import actions as action_catalogue
from pawz.i18n import AUTO, LANGUAGES, tr
from pawz.infra.debug_events import RawInputListener, WindowsEventSources
from pawz.infra.startup import configure_startup
from pawz.infra.storage import DATA_DIR, save
from pawz.ui import artwork_styles
from pawz.ui.controller_assets import SvgView, renderer_for, resolve_artwork
from pawz.ui.controllers_page import ControllersPage, model_name
from pawz.ui.rendering import ScalableIconLabel, configure_text_rendering, vector_icon
from pawz.ui.themes import THEMES, themed

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
APP_ICON = ASSETS_DIR / "logo.svg"
RESTART_FLAG = "--after-exit-of"  # followed by the PID the new instance waits for
SECTION_CONTENT_GAP = 18
CONTROL_ROW_GAP = 12
SHORTCUT_ROW_GAP = 6
SHORTCUT_PROMPT_WIDTH = 72
SHORTCUT_PROMPT_HEIGHT = 24
_LOADED_FONT_PATHS: set[Path] = set()


def load_fonts():
    inter_fonts = ASSETS_DIR / "fonts"
    font_paths = [
        inter_fonts / "Inter-Regular.ttf",
        inter_fonts / "Inter-SemiBold.ttf",
        inter_fonts / "MatchaStyle.ttf",
    ]

    for font_path in font_paths:
        if font_path in _LOADED_FONT_PATHS:
            continue
        if not font_path.is_file():
            raise RuntimeError(f"Missing bundled font: {font_path.name}")
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id < 0:
            if font_path.parent == inter_fonts:
                raise RuntimeError(f"Unable to load bundled font: {font_path}")
            continue
        _LOADED_FONT_PATHS.add(font_path)

    if QApplication.instance() is not None:
        configure_text_rendering(QApplication.instance())


def profile_action_button(title: str, action: str, parent=None) -> QPushButton:
    button = QPushButton(parent)
    button.setAccessibleName(title)
    button.setToolTip(title)
    button.setFixedSize(34, 34)
    button.setIconSize(QSize(18, 18))
    button.setIcon(vector_icon({"duplicate": "duplicate", "edit": "pencil", "delete": "cross"}[action]))
    _style_profile_button(button, padding="0", radius=7)
    button.setStyleSheet(button.styleSheet() + themed(
        "QPushButton:disabled { background:#20385c; border-color:#405b7d; }"))
    return button


def action_icon(kind: str) -> QIcon:
    return vector_icon(kind)


def cross_icon() -> QIcon:
    return vector_icon("cross")


def pencil_icon() -> QIcon:
    return vector_icon("pencil")


CSS = """
QWidget { color:#f5f7fb; font: 10pt 'Inter 18pt'; }
QMainWindow, QDialog { background:#223d68; }
QToolTip { color:#f5f7fb; background:#1b355b; border:1px solid #4b6c97; padding:4px 7px; }
QWidget#mainSurface { background:#223d68; border:1px solid #627895; }
QWidget#mainSurface QWidget { font:13pt 'Inter 18pt'; }
QWidget#mainSurface QWidget#controllerSlot QLabel#controllerName { font:10pt 'Inter 18pt'; }
QWidget#mainSurface QWidget#controllerSlot QLabel#batteryLabel { font:9.1pt 'Inter 18pt'; }
QWidget#mainSurface QWidget#controllerSlot QComboBox#profilePicker { font:9.1pt 'Inter 18pt'; }
QWidget#mainSurface QWidget#controllerSlot QPushButton#forgetController,
QWidget#mainSurface QWidget#controllerSlot QPushButton#setPrimary { font:9.1pt 'Inter 18pt'; }
QWidget#mainSurface QPushButton#primaryAction { font:11.8pt 'Inter 18pt'; }
QWidget#mainSurface QPushButton#windowControl { font:22pt 'Inter 18pt'; }
QLabel#settingsBrand { color:#3989cf; font: 18.7pt 'Matcha Style'; }
QWidget#settingsPage { background:transparent; border:0; }
QWidget#settingsHeader { background:#223d68; }
QTabWidget#settingsTabs { background:transparent; }
QTabWidget#settingsTabs::pane { background:#1b355b; border:1px solid #4b83bd; border-top-left-radius:0px; border-top-right-radius:8px; border-bottom-left-radius:8px; border-bottom-right-radius:8px; top:-1px; }
QTabWidget#settingsTabs QTabBar::tab { color:#f5f7fb; background:#1b355b; border:1px solid #4b83bd; border-top-left-radius:9px; border-top-right-radius:9px; padding:8px 26px; min-width:78px; }
QTabWidget#settingsTabs QTabBar::tab:selected { color:#ffffff; background:#1b355b; border:1px solid #4b83bd; border-bottom:0; font-weight:bold; }
QWidget#activeTabSeam { background:#1b355b; border:0; }
QPushButton#settingsAction, QPushButton#openDebugWindow { color:#ffffff; background:#20527b; border:1px solid #3187c7; border-radius:6px; padding:6px 12px; }
QPushButton#settingsAction:hover, QPushButton#openDebugWindow:hover, QPushButton#removeBinding:hover, QPushButton#removeSection:hover { background:#28618e; }
QPushButton#settingsFooter { background:#20527b; border:1px solid #3187c7; border-radius:7px; padding:7px 20px; min-width:105px; }
QPushButton#hotkeyButton { color:#ffffff; background:#20527b; border:1px solid #3187c7; border-radius:5px; padding:2px 4px; min-width:28px; min-height:30px; }
QPushButton#hotkeyButton:focus { border:2px solid #65baff; }
QPushButton#removeSection { color:#ffffff; background:#20527b; border:1px solid #3187c7; border-radius:5px; padding:0; }
QPushButton#editBinding, QPushButton#removeBinding { color:#ffffff; background:transparent; border:0; padding:0; }
QPushButton#editBinding:hover, QPushButton#removeBinding:hover { background:transparent; border:0; }
QWidget#profileEditor QFrame#bindingRowSeparator { background:#31557e; border:0; }
QWidget#profileEditor QSlider::groove:horizontal { height:4px; background:#10233f; border:0; border-radius:2px; }
QWidget#profileEditor QSlider::sub-page:horizontal { background:#3187c7; border-radius:2px; }
QWidget#profileEditor QSlider::add-page:horizontal { background:#10233f; border:0; border-radius:2px; }
QWidget#profileEditor QSlider::handle:horizontal { background:#3187c7; border:1px solid #65baff; width:12px; height:12px; margin:-5px 0; border-radius:6px; }
QWidget#profileEditor QSlider:disabled::handle:horizontal { background:#526b8b; border-color:#7186a4; }
QFrame#profileSectionBorder { background:transparent; border:1px solid #4b83bd; border-radius:16px; }
QFrame#profileSectionActions { background:#17345e; border-bottom-left-radius:15px; border-bottom-right-radius:15px; }
QFrame#profileSectionActionsSeparator { color:#4b83bd; background:#4b83bd; border:0; }
QWidget#profileSectionHeader { background:transparent; }
QFrame#profileSectionRule { color:#4b83bd; background:#4b83bd; border:0; }
QLabel#profileSectionTitle { color:#ffffff; background:#1b355b; padding:0 5px; }
QLabel#profileSectionIcon { background:#1b355b; }
QWidget#profileSectionContent { background:transparent; }
QFrame#settingsSectionSeparator { color:#4b83bd; background:#4b83bd; border:0; }
QFrame#addProfileSeparator { color:#4b83bd; background:#4b83bd; border:0; }
QScrollArea#profileScroll QFrame#settingsSectionSeparator { color:#4b83bd; background:#4b83bd; border:0; }
QWidget#profileSectionHeading QFrame#settingsSectionSeparator { color:#4b83bd; background:#4b83bd; border:0; }
QWidget#profileSectionHeading { background:transparent; }
QLabel#profileSectionHeadingLabel { color:#ffffff; background:#1b355b; }
QWidget#minimizedOption, QWidget#debugStartupOption { background:transparent; }
QWidget#sectionHeading { background:transparent; }
QLabel#sectionHeadingLabel { color:#ffffff; }
QFrame#sectionHeadingLine { color:#4b83bd; background:#4b83bd; border:0; }
QLabel#controllerName { color:#f4f6fb; font: 11pt 'Inter 18pt'; }
QLabel#controllerName[connected="false"] { color:#5b7192; }
QLabel#batteryLabel { color:#f4f6fb; font: 10pt 'Inter 18pt'; }
QWidget#controllerSlot QLabel#controllerName { color:#f4f6fb; font: 7.7pt 'Inter 18pt'; }
QWidget#controllerSlot QLabel#controllerName[connected="false"] { color:#5b7192; }
QWidget#controllerSlot QLabel#batteryLabel { color:#f4f6fb; font: 7pt 'Inter 18pt'; }
QWidget#controllerSlot QComboBox#profilePicker { font: 7pt 'Inter 18pt'; padding:3px 5px; min-height:15px; }
QWidget#controllerSlot QPushButton#forgetController { font: 7pt 'Inter 18pt'; padding:2px 5px; }
QWidget#controllerSlot QPushButton#setPrimary { font: 7pt 'Inter 18pt'; padding:3px 6px; }
QPushButton#windowControl { color:#9cb4d3; background:transparent; border:0; font: 22pt 'Inter 18pt'; padding:0; }
QPushButton#windowControl:hover { color:#ffffff; }
QPushButton#profilePicker { color:#ffffff; background:#20527b; border:1.5px solid #3187c7; border-radius:8px; padding:5px 12px; text-align:left; min-height:22px; }
QPushButton#profilePicker:hover { background:#28618e; }
QComboBox#profilePicker { color:#ffffff; background:#20527b; border:1.5px solid #3187c7; border-radius:8px; padding:5px 10px; min-height:22px; }
QComboBox#profilePicker QAbstractItemView { color:#f5f7fb; background:#1b355b; border:1px solid #4b6c97; selection-color:#ffffff; selection-background-color:#2765cc; outline:0; }
QComboBox#profilePicker QAbstractItemView::item { min-height:28px; padding:4px 10px; }
QComboBox#profilePicker QAbstractItemView::item:hover { background:#28618e; }
QComboBox#settingsProfilePicker, QComboBox#defaultAssignedProfile { color:#f5f7fb; background:#1b355b; border:1px solid #4b6c97; border-radius:7px; padding:6px 8px; min-height:20px; }
QComboBox#settingsProfilePicker::drop-down, QComboBox#defaultAssignedProfile::drop-down { width:24px; background:#20527b; border-left:1px solid #3187c7; border-top-right-radius:6px; border-bottom-right-radius:6px; }
QComboBox#settingsProfilePicker::down-arrow, QComboBox#defaultAssignedProfile::down-arrow { image:url("__COMBO_ARROW__"); width:10px; height:7px; }
QMenu#trayMenu { color:#f5f7fb; background:#1b355b; border:1px solid #4b6c97; padding:5px; }
QMenu#trayMenu::item { padding:7px 28px 7px 12px; background:transparent; }
QMenu#trayMenu::item:selected { color:#ffffff; background:#2765cc; }
QMenu#trayMenu::separator { height:1px; background:#4b6c97; margin:4px 8px; }
QPushButton#primaryAction { color:#ffffff; background:#20527b; border:2px solid #3187c7; border-radius:7px; font: 9.1pt 'Inter 18pt'; }
QPushButton#primaryAction:hover { background:#28618e; border-color:#54a5e0; }
QPushButton#setPrimary { color:#ffffff; background:#20527b; border:2px solid #3187c7; border-radius:8px; font: 10pt 'Inter 18pt'; padding:5px 10px; }
QPushButton#setPrimary:hover { background:#28618e; }
QFrame#separator { color:#3e5e8b; background:#3e5e8b; border:0; }
QGroupBox { border:1px solid #4d6c95; border-radius:12px; margin-top:16px; padding:16px 10px 10px; font-weight:600; }
QGroupBox::title { subcontrol-origin:margin; left:16px; padding:0 6px; color:#b9d5ff; }
QPushButton { background:#20527b; border:1px solid #3187c7; border-radius:8px; padding:8px 14px; }
QPushButton:hover { background:#28618e; }
QPushButton:disabled { background:#2b4265; color:#7186a4; }
QComboBox, QLineEdit { color:#f5f7fb; background:#1b355b; border:1px solid #4b6c97; border-radius:7px; padding:6px 8px; min-height:20px; }
QComboBox::drop-down { width:24px; background:#20527b; border-left:1px solid #3187c7; border-top-right-radius:6px; border-bottom-right-radius:6px; }
QComboBox::down-arrow { image:url("__COMBO_ARROW__"); width:10px; height:7px; }
QComboBox QAbstractItemView { color:#f5f7fb; background:#1b355b; border:1px solid #4b6c97; selection-color:#ffffff; selection-background-color:#2765cc; outline:0; }
QComboBox QAbstractItemView::item { min-height:28px; padding:4px 10px; }
QComboBox QAbstractItemView::item:hover { background:#28618e; }
QComboBox QAbstractItemView::item:selected { color:#ffffff; background:#2765cc; }
QCheckBox { spacing:8px; }
QCheckBox::indicator { width:15px; height:15px; border:1px solid #4b83bd; border-radius:3px; background:#1b355b; }
QCheckBox::indicator:hover { border-color:#65baff; }
QCheckBox::indicator:checked { image:url("__CHECKBOX_CHECK__"); background:#2765cc; border-color:#54a5e0; }
QScrollArea { border:0; }
QScrollArea#controllersScroll, QWidget#controllersContent { background:#1b355b; }
QTableWidget#controllerCorrespondences, QTableWidget#controllerIdentification { background:#1b355b; color:#ffffff; gridline-color:#4b83bd; border:1px solid #4b83bd; }
QHeaderView::section { background:#17345e; color:#ffffff; border:1px solid #4b83bd; padding:6px; }
QScrollArea#controllerScroll { background:transparent; }
QScrollArea#controllerScroll QWidget { background:transparent; }
QScrollArea#profileScroll { background:transparent; }
QScrollArea#profileScroll QWidget { background:transparent; }
QScrollBar:vertical { width:8px; background:transparent; margin:0; border:0; }
QScrollBar::handle:vertical { background:#20527b; border:1px solid #3187c7; border-radius:4px; min-height:36px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; background:transparent; border:0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background:transparent; }
QTabWidget::pane { background:#223d68; border:1px solid #4d6c95; border-radius:8px; }
QTabBar::tab { color:#b9d5ff; background:#1b355b; border:1px solid #4b6c97; border-bottom:0; border-top-left-radius:7px; border-top-right-radius:7px; padding:8px 18px; }
QTabBar::tab:selected { color:#ffffff; background:#20527b; border-color:#3187c7; }
QLabel#debugHeading { color:#3989cf; font: 30pt 'Matcha Style'; }
QTextEdit#debugEventList { color:#f5f7fb; background:#1b355b; border:1px solid #20385c; border-radius:10px; padding:10px; font: 10pt 'Inter 18pt'; }
QPushButton:checked { background:#28618e; border-color:#54a5e0; }
"""
CSS = CSS.replace(
    "__COMBO_ARROW__", (ASSETS_DIR / "combo-arrow.svg").as_posix())
CSS = CSS.replace(
    "__CHECKBOX_CHECK__", (ASSETS_DIR / "checkbox-check.svg").as_posix())


def stylesheet() -> str:
    """The application stylesheet in the current theme (``CSS`` is Midnight Blue)."""
    return themed(CSS)


def _set_separator_overlay(widget: QWidget) -> None:
    widget.setStyleSheet(themed("background-color:#1b355b;"))


def _style_profile_button(button: QPushButton, *, padding: str = "0",
                          radius: int = 5, focus: bool = False) -> None:
    focus_rule = (
        "QPushButton:focus { border:2px solid #65baff; }" if focus else "")
    button.setStyleSheet(themed(
        "QPushButton { color:#ffffff; background:#20527b; "
        f"border:1px solid #3187c7; border-radius:{radius}px; padding:{padding}; }}"
        "QPushButton:hover { background:#28618e; }"
        + focus_rule))


class ProfileDialog(QDialog):
    def __init__(self, profile: Profile, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Edit profile — {name}").format(name=profile.name))
        self.resize(790, 680)
        self.setObjectName("profileDialog")
        root = QVBoxLayout(self)
        title = QLabel(tr("Shortcuts · {name}").format(name=profile.name))
        title.setObjectName("heading")
        root.addWidget(title)
        self.editor = ProfileEditor(profile, self)
        root.addWidget(self.editor, 1)
        save_btn = QPushButton(tr("Save profile"))
        save_btn.clicked.connect(self.accept)
        root.addWidget(save_btn)

    @property
    def profile(self) -> Profile:
        return self.editor.profile


class SettingsTabWidget(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsTabs")
        self.tabBar().setUsesScrollButtons(False)
        self._active_tab_seam = QWidget(self)
        self._active_tab_seam.setObjectName("activeTabSeam")
        self.currentChanged.connect(self._position_active_tab_seam)
        self._seam_timer = QTimer(self)
        self._seam_timer.setSingleShot(True)
        self._seam_timer.setInterval(0)
        self._seam_timer.timeout.connect(self._position_active_tab_seam)
        self.currentChanged.connect(lambda *_: self._seam_timer.start())
        self._active_tab_seam.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._seam_timer.start()

    def showEvent(self, event):
        super().showEvent(event)
        self._seam_timer.start()

    def _position_active_tab_seam(self, *_):
        index = self.currentIndex()
        if index < 0:
            self._active_tab_seam.hide()
            return
        tab_rect = self.tabBar().tabRect(index)
        stack = self.widget(index).parentWidget()
        stack_top = stack.mapTo(self, QPoint(0, 0)).y()
        self._active_tab_seam.setGeometry(
            self.tabBar().x() + tab_rect.x(),
            stack_top,
            tab_rect.width(),
            1,
        )
        self._active_tab_seam.show()
        self._active_tab_seam.raise_()


class ProfileSectionFrame(QFrame):
    HEADER_OVERLAP = 15
    REMOVE_BUTTON_OVERLAP = 11

    def __init__(self, parent=None):
        super().__init__(parent)
        self._header: QWidget | None = None
        self._content: QWidget | None = None
        self._actions: QWidget | None = None
        self._border = QFrame(self)
        self._border.setObjectName("profileSectionBorder")
        self._border_layout = QVBoxLayout(self._border)
        self._border_layout.setContentsMargins(0, 0, 0, 0)

    def set_section_widgets(self, header: QWidget, content: QWidget, actions: QWidget):
        self._header = header
        self._content = content
        self._actions = actions
        header.setParent(self)
        content.setParent(self._border)
        self._border_layout.addWidget(content)
        actions.setParent(self._border)
        self._border_layout.addWidget(actions)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        border_width = self.width()
        if self._header is not None and isinstance(self._header, ProfileSectionHeader):
            if self._header.remove_button is not None:
                border_width = max(0, border_width - self.REMOVE_BUTTON_OVERLAP)
        self._border.setGeometry(
            0, self.HEADER_OVERLAP, border_width,
            max(0, self.height() - self.HEADER_OVERLAP))
        if self._header is not None:
            self._header.setGeometry(
                0, 0, self.width(),
                self.HEADER_OVERLAP * 2)
            self._header.raise_()

    def sizeHint(self) -> QSize:
        if self._content is None or self._actions is None:
            return super().sizeHint()
        content_size = self._content.sizeHint()
        actions_size = self._actions.sizeHint()
        return QSize(
            max(content_size.width(), actions_size.width()),
            content_size.height() + actions_size.height() + self.HEADER_OVERLAP)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()


class ProfileSectionHeading(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("profileSectionHeading")
        self.label = QLabel(title.upper(), self)
        self.label.setObjectName("profileSectionHeadingLabel")
        _set_separator_overlay(self.label)
        self.rule = QFrame(self)
        self.rule.setObjectName("settingsSectionSeparator")
        self.setFixedHeight(28)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.label.adjustSize()
        self.label.move(10, (self.height() - self.label.height()) // 2)
        line_start = self.label.geometry().right() + 8
        self.rule.setGeometry(
            line_start, self.height() // 2, max(0, self.width() - line_start - 10), 1)
        self.label.raise_()


class ProfileSectionHeader(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.remove_button: QPushButton | None = None
        self.rule = QFrame(self)
        self.rule.setObjectName("profileSectionRule")
        self.rule.lower()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        rule_width = self.width()
        if self.remove_button is not None:
            rule_width -= (self.remove_button.width() + 1) // 2
            self.remove_button.move(
                self.width() - self.remove_button.width(),
                self.height() // 2 - (self.remove_button.height() - 1) // 2)
        self.rule.setGeometry(0, self.height() // 2, max(0, rule_width), 1)


def executable_list(text: str) -> list[str]:
    """``"Game.exe, other.exe"`` -> ``["game.exe", "other.exe"]``."""
    return [name.strip().lower() for name in text.replace(";", ",").split(",") if name.strip()]


class ProfileEditor(QWidget):
    ACTION_LABELS = action_catalogue.LABELS
    BUTTON_LABELS = {
        "a": "A", "b": "B", "x": "X", "y": "Y", "l": "L", "r": "R",
        "minus": "MINUS", "plus": "PLUS", "home": "HOME",
        "right_stick": "RS", "dpad_up": "↑", "dpad_down": "↓",
        "dpad_left": "←", "dpad_right": "→",
    }

    def __init__(self, profile: Profile, parent=None, controller_manager=None, display_model=None):
        super().__init__(parent)
        self.profile = copy.deepcopy(profile)
        self.controller_manager = controller_manager
        self.display_model = display_model
        self._capturing: tuple[dict[str, Binding], str, Binding, QPushButton] | None = None
        self._capture_device: str | None = None
        if controller_manager is not None:
            controller_manager.controller_button_event.connect(self._capture_input_event)
        self.setObjectName("profileEditor")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("profileScroll")
        scroll.viewport().setAutoFillBackground(False)
        scroll.setWidgetResizable(True)
        host = QWidget()
        host.setAutoFillBackground(False)
        self.sections = QVBoxLayout(host)
        self.sections.setContentsMargins(4, 8, 12, 8)
        self.sections.setSpacing(10)
        scroll.setWidget(host)
        root.addWidget(scroll)
        self.draw()

    def _magnet_control(self) -> QWidget:
        control = QWidget()
        control.setObjectName("magnetControl")
        column = QVBoxLayout(control)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)
        magnet = QSlider(Qt.Orientation.Horizontal)
        magnet.setObjectName("magnetStrength")
        magnet.setStyleSheet(themed("background:#1b355b; border:0;"))
        magnet.setRange(10, 100)
        magnet.setValue(round(self.profile.magnet_strength))
        magnet.setToolTip(tr("Pull strength, and the effort needed to break free of a target"))
        magnet_value = QLabel(tr("{value}%").format(value=magnet.value()))
        magnet_value.setMinimumWidth(48)
        magnet_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        def update_strength(value):
            self.profile.magnet_strength = float(value)
            magnet_value.setText(tr("{value}%").format(value=value))

        magnet.valueChanged.connect(update_strength)
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(12)
        row_layout.addWidget(magnet, 1)
        row_layout.addWidget(magnet_value)
        column.addWidget(row)
        for name, text, tip, attr in (
                ("magnetAuto", tr("Automatic"),
                 tr("Always on. When unchecked, magnetism only works while the "
                    "right trigger (ZR) is held."), "magnet_auto"),
                ("magnetBackground", tr("Include background windows"),
                 tr("The edges and buttons of visible windows behind the active "
                    "window also attract the pointer."), "magnet_background"),
                ("magnetHaptics", tr("Vibrate on capture and release"),
                 tr("A short controller vibration when the pointer is caught "
                    "by a target and when it breaks free."), "magnet_haptics")):
            box = QCheckBox(text)
            box.setObjectName(name)
            box.setToolTip(tip)
            box.setChecked(getattr(self.profile, attr))
            box.toggled.connect(lambda checked, key=attr: setattr(self.profile, key, checked))
            column.addWidget(box)
        return control

    def draw(self):
        while self.sections.count():
            item = self.sections.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        self._heading(tr("Sensitivity"))
        group = QWidget()
        layout = QFormLayout(group)
        layout.setContentsMargins(22, 0, 22, 8)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(CONTROL_ROW_GAP)
        mouse_control = QWidget()
        mouse_layout = QVBoxLayout(mouse_control)
        mouse_layout.setContentsMargins(0, 0, 0, 0)
        mouse_layout.setSpacing(8)
        control, slider, value_label = self._slider_control(
            "mouse_speed", self.profile.mouse_speed, 1, 50, 100)
        mouse_layout.addWidget(control)
        slider.valueChanged.connect(lambda value: self._set_profile_value(
            "mouse_speed", value / 100, value_label))
        mouse_control.setObjectName("mouseSensitivityControl")
        mouse_label = QLabel(tr("Mouse"))
        mouse_label.setMinimumWidth(108)
        mouse_label.setObjectName("mouseSpeedLabel")
        layout.addRow(mouse_label, mouse_control)
        magnet_label = QLabel(tr("Magnetism"))
        magnet_label.setMinimumWidth(108)
        magnet_label.setObjectName("magnetLabel")
        layout.addRow(magnet_label, self._magnet_control())

        for label, attr, low, high, scale in (
                (tr("Scroll wheel"), "scroll_speed", .1, 15, 10),
                (tr("Dead zone"), "deadzone", 0, .9, 100)):
            control, slider, value_label = self._slider_control(
                attr, getattr(self.profile, attr), low, high, scale)
            label_widget = QLabel(label)
            label_widget.setMinimumWidth(108)
            label_widget.setObjectName(
                "scrollSpeedLabel" if attr == "scroll_speed" else "deadzoneLabel")
            layout.addRow(label_widget, control)
            slider.valueChanged.connect(
                lambda value, key=attr, factor=scale, text=value_label:
                self._set_profile_value(key, value / factor, text))
        self.sections.addWidget(group)
        self._heading(tr("Navigation"))
        self._section(tr("General"), self.profile.global_bindings)

        if self.profile.apps:
            self._heading(tr("Applications"))
        add_app = QPushButton(tr("Add an application..."), self)
        add_app.setObjectName("settingsAction")
        _style_profile_button(add_app, padding="6px 12px", radius=6)
        add_app.ensurePolished()
        add_app.setFixedWidth(2 * add_app.sizeHint().width())
        add_app.clicked.connect(self.add_app)
        self.sections.addWidget(add_app, 0, Qt.AlignmentFlag.AlignHCenter)
        for name, bindings in self.profile.apps.items():
            self._section(self._application_name(name), bindings,
                          lambda selected=name: self._remove_context(self.profile.apps, selected),
                          self._application_icon(name))
        if self.profile.sites:
            self._heading(tr("Websites"))
        add_site = QPushButton(tr("Add a website..."), self)
        add_site.setObjectName("settingsAction")
        _style_profile_button(add_site, padding="6px 12px", radius=6)
        add_site.ensurePolished()
        add_site.setFixedWidth(2 * add_site.sizeHint().width())
        add_site.clicked.connect(self.add_site)
        self.sections.addWidget(add_site, 0, Qt.AlignmentFlag.AlignHCenter)
        for name, bindings in self.profile.sites.items():
            self._section(name, bindings,
                          lambda selected=name: self._remove_context(self.profile.sites, selected),
                          self._site_icon(name))

    @staticmethod
    def _slider_control(name: str, current: float, low: float, high: float,
                        scale: int) -> tuple[QWidget, QSlider, QLabel]:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setObjectName(name)
        slider.setStyleSheet(themed("background:#1b355b; border:0;"))
        slider.setRange(round(low * scale), round(high * scale))
        slider.setValue(round(current * scale))
        value_label = QLabel(QLocale().toString(float(current), "f", 2))
        value_label.setMinimumWidth(48)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(slider, 1)
        row.addWidget(value_label)
        return container, slider, value_label

    def _set_profile_value(self, key: str, value: float, label: QLabel):
        setattr(self.profile, key, value)
        label.setText(QLocale().toString(float(value), "f", 2))

    @staticmethod
    def _application_name(executable: str) -> str:
        names = {"brave.exe": "Brave", "firefox.exe": "Firefox", "chrome.exe": "Chrome",
                 "msedge.exe": "Edge", "vlc.exe": "VLC"}
        return names.get(executable.lower(), Path(executable).stem)

    @staticmethod
    def _application_icon(executable: str) -> QIcon:
        roots = (
            Path(os.environ.get("ProgramFiles", "C:\\Program Files")),
            Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")),
            Path(os.environ.get("LOCALAPPDATA", "")),
        )
        subpaths = {
            "brave.exe": ("BraveSoftware/Brave-Browser/Application/brave.exe",),
            "firefox.exe": ("Mozilla Firefox/firefox.exe",),
            "chrome.exe": ("Google/Chrome/Application/chrome.exe",),
            "msedge.exe": ("Microsoft/Edge/Application/msedge.exe",),
            "vlc.exe": ("VideoLAN/VLC/vlc.exe",),
        }
        candidates = [
            root / relative
            for root in roots
            for relative in subpaths.get(executable.lower(), ())
        ]
        application_path = next((path for path in candidates if path.is_file()), None)
        if application_path is None or os.name != "nt":
            return QIcon()

        large_icons = (ctypes.c_void_p * 1)()
        small_icons = (ctypes.c_void_p * 1)()
        extract_icons = ctypes.windll.shell32.ExtractIconExW
        extract_icons.argtypes = (
            ctypes.c_wchar_p, ctypes.c_int,
            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_uint,
        )
        extract_icons.restype = ctypes.c_uint
        count = extract_icons(
            str(application_path), 0, large_icons, small_icons, 1)
        if not count:
            return QIcon()
        icon_handles = (large_icons[0], small_icons[0])
        try:
            handle = next((icon for icon in icon_handles if icon), None)
            if handle is None:
                return QIcon()
            return QIcon(QPixmap.fromImage(QImage.fromHICON(handle)))
        finally:
            destroy_icon = ctypes.windll.user32.DestroyIcon
            destroy_icon.argtypes = (ctypes.c_void_p,)
            for handle in set(icon for icon in icon_handles if icon):
                destroy_icon(handle)

    @staticmethod
    def _site_icon(domain: str) -> QIcon:
        if domain.lower().removeprefix("www.") != "youtube.com":
            return QIcon()
        return vector_icon("youtube")

    def _heading(self, title: str):
        self.sections.addSpacing(16)
        self.sections.addWidget(ProfileSectionHeading(title))
        self.sections.addSpacing(SECTION_CONTENT_GAP - self.sections.spacing())

    def _section(self, name: str, bindings: dict[str, Binding], remove=None,
                 icon: QIcon | None = None):
        group = ProfileSectionFrame()
        group.setObjectName("profileSectionFrame")
        header = ProfileSectionHeader()
        header.setObjectName("profileSectionHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 0, 0, 0)
        header_layout.setSpacing(0)
        if icon is not None and not icon.isNull():
            icon_label = ScalableIconLabel(icon, QSize(16, 22))
            icon_label.setObjectName("profileSectionIcon")
            _set_separator_overlay(icon_label)
            icon_label.setFixedSize(16, 22)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header_layout.addWidget(icon_label)
        title = QLabel(name)
        title.setObjectName("profileSectionTitle")
        _set_separator_overlay(title)
        title.setStyleSheet(themed("background-color:#1b355b; padding:0 2px;"))
        title.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        header_layout.addWidget(title, 0)
        header_layout.addStretch(1)
        if remove is not None:
            remove_button = QPushButton(header)
            remove_button.setObjectName("removeSection")
            _style_profile_button(remove_button)
            remove_button.setAccessibleName(tr("Remove"))
            remove_button.setToolTip(tr("Remove"))
            remove_button.setIcon(cross_icon())
            remove_button.setIconSize(QSize(16, 16))
            remove_button.setFixedSize(21, 21)
            remove_button.clicked.connect(remove)
            header.remove_button = remove_button
        content = QWidget()
        content.setObjectName("profileSectionContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 18, 24, 18)
        content_layout.setSpacing(SHORTCUT_ROW_GAP)
        for index, trigger in enumerate(sorted(
                bindings,
                key=lambda value: tuple(BUTTONS.index(item) for item in value.split("+")))):
            if index:
                separator = QFrame()
                separator.setObjectName("bindingRowSeparator")
                separator.setFixedHeight(1)
                content_layout.addWidget(separator)
            binding = bindings[trigger]
            row = QGridLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setHorizontalSpacing(8)
            row.setColumnStretch(0, 1)
            row.setColumnStretch(2, 1)
            label = QLabel(tr(self.ACTION_LABELS.get(binding.action, binding.action)))
            label.setObjectName("bindingAction")
            row.addWidget(label, 0, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            hotkey = SvgView()
            hotkey.setObjectName("bindingPrompt")
            hotkey.setFixedSize(SHORTCUT_PROMPT_WIDTH, SHORTCUT_PROMPT_HEIGHT)
            hotkey.set_render_scale(0.9)
            hotkey.set_controller_prompt(trigger, self.display_model)
            hotkey.setToolTip(trigger)
            row.addWidget(hotkey, 0, 1, Qt.AlignmentFlag.AlignCenter)
            edit = QPushButton()
            edit.setIcon(pencil_icon())
            edit.setIconSize(QSize(14, 14))
            edit.setObjectName("editBinding")
            edit.setAccessibleName(tr("Edit shortcut"))
            edit.setToolTip(tr("Edit shortcut"))
            edit.setFixedSize(24, 24)
            edit.setFlat(True)
            edit.setCursor(Qt.CursorShape.PointingHandCursor)
            edit.clicked.connect(lambda _checked=False, d=bindings, t=trigger: self.edit_binding(d, t))
            row.addWidget(edit, 0, 3, Qt.AlignmentFlag.AlignCenter)
            remove = QPushButton()
            remove.setObjectName("removeBinding")
            remove.setFlat(True)
            remove.setCursor(Qt.CursorShape.PointingHandCursor)
            remove.setAccessibleName(tr("Remove shortcut"))
            remove.setToolTip(tr("Remove shortcut"))
            remove.setIcon(cross_icon())
            remove.setIconSize(QSize(14, 14))
            remove.setFixedSize(24, 24)
            remove.clicked.connect(lambda _checked=False, b=trigger, d=bindings: self._remove(d, b))
            row.addWidget(remove, 0, 4, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            content_layout.addLayout(row, 0)
        actions = QFrame()
        actions.setObjectName("profileSectionActions")
        actions.setStyleSheet(themed(
            "background:#17345e; border-bottom-left-radius:15px; "
            "border-bottom-right-radius:15px;"))
        actions_layout = QVBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 14)
        actions_layout.setSpacing(10)
        separator = QFrame()
        separator.setObjectName("profileSectionActionsSeparator")
        separator.setStyleSheet(themed("background:#4b83bd; border:0;"))
        separator.setFixedHeight(1)
        actions_layout.addWidget(separator)
        add = QPushButton(tr("Add a shortcut..."))
        add.setObjectName("settingsAction")
        _style_profile_button(add, padding="6px 12px", radius=6)
        add.clicked.connect(lambda _checked=False, target=bindings: self.add_binding(target))
        actions_layout.addWidget(add, 0, Qt.AlignmentFlag.AlignHCenter)
        group.set_section_widgets(header, content, actions)
        self.sections.addWidget(group)

    def _trigger_label(self, trigger: str) -> str:
        return " + ".join(
            self.BUTTON_LABELS.get(button, button.upper()) for button in trigger.split("+"))

    def edit_binding(self, bindings, trigger):
        dialog = QDialog(self)
        dialog.setObjectName("bindingEditor")
        dialog.setWindowTitle(tr("Edit shortcut"))
        form = QFormLayout(dialog)
        buttons = QLineEdit(trigger)
        buttons.setObjectName("bindingLogicalInput")
        action = QComboBox()
        action.setObjectName("bindingWindowsAction")
        for value in ACTIONS:
            action.addItem(tr(self.ACTION_LABELS[value]), value)
        binding = bindings[trigger]
        action.setCurrentIndex(action.findData(binding.action))
        keys = QLineEdit(binding.keys)
        scope = QComboBox()
        scope.addItems([tr("General"), tr("Application"), tr("Website")])
        context = QLineEdit()
        for index, contexts in ((1, self.profile.apps), (2, self.profile.sites)):
            for name, mapping in contexts.items():
                if mapping is bindings:
                    scope.setCurrentIndex(index)
                    context.setText(name)
        form.addRow(tr("Logical buttons (+ to combine)"), buttons)
        form.addRow(tr("Windows action"), action)
        form.addRow(tr("Keyboard keys"), keys)
        form.addRow(tr("Condition"), scope)
        form.addRow(tr("Application (.exe) or domain"), context)
        capture = QPushButton(tr("Record a combination with the controller…"))
        capture.setEnabled(self.controller_manager is not None)
        form.addRow(capture)
        captured = []
        capture_device = [None]
        capturing = [False]
        def capture_event(device, button, pressed):
            if not capturing[0] or (capture_device[0] and capture_device[0] != device):
                return
            if pressed:
                capture_device[0] = device
                if button not in captured:
                    captured.append(button)
                buttons.setText("+".join(captured))
            elif captured:
                capturing[0] = False
                self.controller_manager.end_input_capture()
                capture.setText(tr("Record a combination with the controller…"))
        def begin_capture():
            captured.clear()
            capture_device[0] = None
            capturing[0] = True
            self.controller_manager.begin_input_capture()
            capture.setText(tr("Press the buttons, then release…"))
        capture.clicked.connect(begin_capture)
        if self.controller_manager:
            self.controller_manager.controller_button_event.connect(capture_event)
        error = QLabel()
        error.setWordWrap(True)
        form.addRow(error)
        controls = QHBoxLayout()
        apply = QPushButton(tr("Save"))
        cancel = QPushButton(tr("Cancel"))
        controls.addWidget(apply)
        controls.addWidget(cancel)
        form.addRow(controls)
        cancel.clicked.connect(dialog.reject)
        def commit():
            try:
                normalized = normalize_trigger(buttons.text())
                name = context.text().strip().lower().removeprefix("www.")
                target = bindings
                if scope.currentIndex() and not name:
                    raise ValueError(tr("Enter an application or a domain"))
                if scope.currentIndex() == 0:
                    target = self.profile.global_bindings
                elif scope.currentIndex() == 1:
                    target = self.profile.apps.get(name, {})
                else:
                    target = self.profile.sites.get(name, {})
                if (target is not bindings or normalized != trigger) and normalized in target:
                    raise ValueError(tr("This button is already assigned in this context"))
                if scope.currentIndex() == 1:
                    self.profile.apps.setdefault(name, target)
                elif scope.currentIndex() == 2:
                    self.profile.sites.setdefault(name, target)
                bindings.pop(trigger)
                target[normalized] = Binding(action.currentData(), keys.text())
                dialog.accept()
            except ValueError as exc:
                error.setText(str(exc))
        apply.clicked.connect(commit)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.draw()
        finally:
            if self.controller_manager:
                self.controller_manager.controller_button_event.disconnect(capture_event)
                if capturing[0]:
                    self.controller_manager.end_input_capture()

    def _begin_capture(self, bindings, trigger, binding, widget):
        if self.controller_manager is None:
            QMessageBox.warning(
                self, tr("Controller required"),
                tr("Connect a controller to record a button or a combination."))
            return
        if self._capturing is not None:
            self._cancel_capture()
        self._capturing = (bindings, trigger, binding, widget)
        self._capture_device = None
        self._captured_buttons: set[str] = set()
        self._capture_order: list[str] = []
        widget.setText("Input...")
        widget.setFocus()
        self.controller_manager.begin_input_capture()

    def _capture_input_event(self, device: str, button: str, pressed: bool):
        if self._capturing is None:
            return
        if pressed:
            if self._capture_device is not None and device != self._capture_device:
                return
            self._capture_device = device
            if button not in self._captured_buttons:
                self._captured_buttons.add(button)
                self._capture_order.append(button)
                self._capturing[3].setText(self._trigger_label("+".join(self._capture_order)))
            return
        if device == self._capture_device and button in self._captured_buttons:
            self._finish_capture()

    def _finish_capture(self):
        if self._capturing is None:
            return
        assert self.controller_manager is not None
        bindings, old_trigger, binding, widget = self._capturing
        self._capturing = None
        self._capture_device = None
        self.controller_manager.end_input_capture()
        if not self._capture_order:
            widget.setText(self._trigger_label(old_trigger))
            return
        new_trigger = normalize_trigger("+".join(self._capture_order))
        if new_trigger != old_trigger and new_trigger in bindings:
            QMessageBox.warning(self, tr("Button already in use"), tr("This button is already assigned."))
            widget.setText(self._trigger_label(old_trigger))
            return
        bindings.pop(old_trigger)
        bindings[new_trigger] = binding
        self.draw()

    def _cancel_capture(self):
        if self._capturing is None:
            return
        assert self.controller_manager is not None
        _, old_trigger, _, widget = self._capturing
        self._capturing = None
        self._capture_device = None
        self.controller_manager.end_input_capture()
        widget.setText(self._trigger_label(old_trigger))

    def cancel_capture(self):
        self._cancel_capture()

    def _remove(self, bindings, button):
        bindings.pop(button, None)
        self.draw()

    def _remove_context(self, contexts, name):
        contexts.pop(name, None)
        self.draw()

    def add_binding(self, bindings):
        actions = [tr(self.ACTION_LABELS[action]) for action in ACTIONS]
        action, ok = QInputDialog.getItem(
            self, tr("Add a shortcut"), tr("Action"), actions, 0, False)
        if ok and action:
            selected = ACTIONS[actions.index(action)]
            available = [button for button in BUTTONS if button not in bindings]
            if not available:
                QMessageBox.warning(self, tr("No button available"),
                                    tr("Remove or replace an existing shortcut."))
                return
            bindings[available[0]] = Binding(selected)
            self.draw()

    def add_app(self):
        # Standard Windows file picker; selecting the executable is more reliable than
        # enumerating uninstall registry entries (portable apps are supported too).
        filename, _ = QFileDialog.getOpenFileName(
            self, tr("Select an installed program"),
            os.environ.get("ProgramFiles", "C:\\Program Files"), tr("Applications (*.exe)"))
        if filename:
            self.profile.apps.setdefault(
                Path(filename).name.lower(),
                {"SOUTH": Binding("play_pause")} if Path(filename).name.lower() == "vlc.exe" else {})
            self.draw()

    def add_site(self):
        domain, ok = QInputDialog.getText(self, tr("Add a website"), tr("Domain (e.g. youtube.com)"))
        domain = domain.strip().lower().removeprefix("www.")
        if ok and domain and "." in domain and "/" not in domain and " " not in domain:
            self.profile.sites.setdefault(domain, {})
            self.draw()


class ProfileCreationDialog(QDialog):
    def __init__(self, models: list[str], parent=None):
        super().__init__(parent)
        self.existing_profiles = set(models)
        self.setWindowTitle(tr("Add a profile"))
        self.setObjectName("profileCreationDialog")
        self.resize(430, 190)
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.name_input = QLineEdit()
        self.name_input.setObjectName("newProfileName")
        form.addRow(tr("Name"), self.name_input)
        self.model_picker = QComboBox()
        self.model_picker.setObjectName("profileModel")
        self.model_picker.addItems(models)
        form.addRow(tr("Model"), self.model_picker)
        root.addLayout(form)
        buttons = QHBoxLayout()
        self.create_button = QPushButton(tr("Create profile"))
        self.create_button.setObjectName("createProfile")
        self.create_button.clicked.connect(self._create)
        self.cancel_button = QPushButton(tr("Cancel"))
        self.cancel_button.setObjectName("cancelProfile")
        self.cancel_button.clicked.connect(self._confirm_cancel)
        buttons.addStretch()
        buttons.addWidget(self.create_button)
        buttons.addWidget(self.cancel_button)
        root.addLayout(buttons)
        self.name_input.textChanged.connect(self._update_create_enabled)
        self._update_create_enabled()

    @property
    def profile_name(self) -> str:
        return self.name_input.text().strip()

    @property
    def model_name(self) -> str:
        return self.model_picker.currentText()

    def _update_create_enabled(self, *_):
        self.create_button.setEnabled(
            bool(self.profile_name) and self.profile_name not in self.existing_profiles)

    def _create(self):
        if not self.profile_name:
            return
        self.accept()

    def _confirm_cancel(self):
        answer = QMessageBox.question(
            self, tr("Cancel creation"),
            tr("Are you sure you want to cancel creating this profile?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.reject()


class DebugWindow(QDialog):
    SOURCES = (
        ("set_windows_hook", "SetWindowsHookEx"),
        ("win_event_hook", "SetWinEventHook"),
        ("uia", "UIA"),
        ("raw_input", "Raw Input"),
        ("etw", "ETW"),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} — Debug")
        self.setObjectName("debugWindow")
        self.setWindowIcon(QIcon(str(APP_ICON)))
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.resize(926, 720)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 8, 16, 16)
        root.setSpacing(12)
        header = DraggableHeader()
        header.setFixedHeight(62)
        header_layout = QGridLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setColumnStretch(0, 1)
        header_layout.setColumnStretch(2, 1)
        title = QWidget()
        title_layout = QHBoxLayout(title)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(7)
        icon = ScalableIconLabel(QIcon(str(APP_ICON)), QSize(32, 32))
        title_layout.addWidget(icon)
        heading = QLabel(tr("DEBUG"))
        heading.setObjectName("debugHeading")
        title_layout.addWidget(heading)
        header_layout.addWidget(title, 0, 1, Qt.AlignmentFlag.AlignCenter)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        minimize = QPushButton("−")
        minimize.setObjectName("windowControl")
        minimize.setFixedSize(34, 30)
        minimize.clicked.connect(self.showMinimized)
        close = QPushButton("×")
        close.setObjectName("windowControl")
        close.setFixedSize(34, 30)
        close.clicked.connect(self.close)
        controls.addWidget(minimize)
        controls.addWidget(close)
        header_layout.addLayout(
            controls, 0, 2, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        root.addWidget(header)

        self.event_list = QTextEdit()
        self.event_list.setObjectName("debugEventList")
        self.event_list.setReadOnly(True)
        self.event_list.document().setMaximumBlockCount(2000)
        root.addWidget(self.event_list, 1)

        self.sources = WindowsEventSources(self)
        self.sources.event_received.connect(self.append_event)
        self.sources.source_error.connect(self._source_error)
        self.raw_input = RawInputListener(self.append_event)
        self._native_filter_installed = False

        buttons = QHBoxLayout()
        buttons.setContentsMargins(52, 0, 52, 0)
        buttons.setSpacing(18)
        self.source_buttons: dict[str, QPushButton] = {}
        for source, label in self.SOURCES:
            button = QPushButton(label)
            button.setObjectName(f"debugSource_{source}")
            button.setCheckable(True)
            button.setMinimumHeight(44)
            button.toggled.connect(
                lambda enabled, selected=source: self.set_source_enabled(selected, enabled))
            self.source_buttons[source] = button
            buttons.addWidget(button, 1)
        root.addLayout(buttons)
        self._install_native_filter()

    def _install_native_filter(self):
        app = QApplication.instance()
        if app is not None and not self._native_filter_installed:
            app.installNativeEventFilter(self.raw_input)
            self._native_filter_installed = True

    def set_source_enabled(self, source: str, enabled: bool):
        try:
            if source == "raw_input":
                self._install_native_filter()
                self.raw_input.set_enabled(enabled, int(self.winId()) if enabled else None)
            else:
                self.sources.set_enabled(source, enabled)
        except Exception as exc:
            button = self.source_buttons[source]
            button.blockSignals(True)
            button.setChecked(False)
            button.blockSignals(False)
            self._source_error(source, str(exc))

    def append_event(self, source: str, event: str):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        source_label = dict(self.SOURCES).get(source, source)
        self.event_list.append(f"{timestamp}  [{source_label}] {event}")

    def _source_error(self, source: str, message: str):
        button = self.source_buttons.get(source)
        if button is not None and button.isChecked():
            button.blockSignals(True)
            button.setChecked(False)
            button.blockSignals(False)
            if source != "raw_input":
                self.sources.set_enabled(source, False)
        self.append_event(source, tr("ERROR: {message}").format(message=message))

    def showEvent(self, event):
        self._install_native_filter()
        super().showEvent(event)

    def closeEvent(self, event):
        self.sources.stop_all()
        if self.raw_input.enabled:
            try:
                self.raw_input.set_enabled(False)
            except OSError as exc:
                self._source_error("raw_input", str(exc))
        for button in self.source_buttons.values():
            button.blockSignals(True)
            button.setChecked(False)
            button.blockSignals(False)
        app = QApplication.instance()
        if app is not None and self._native_filter_installed:
            app.removeNativeEventFilter(self.raw_input)
            self._native_filter_installed = False
        super().closeEvent(event)


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None, debug_window: DebugWindow | None = None,
                 initial_tab: str | None = None, controller_manager=None):
        super().__init__(parent)
        self.settings = copy.deepcopy(settings)
        settings = self.settings
        self.catalog = ControllerCatalog(DATA_DIR / "controllers" / "catalog.json")
        self.debug_window = debug_window
        self.controller_manager = controller_manager
        self.profiles = settings.profiles
        self.current_profile_name: str | None = None
        self.profile_editor: ProfileEditor | None = None
        self.setWindowTitle(tr("Settings"))
        self.setObjectName("settingsDialog")
        self.setWindowIcon(QIcon(str(APP_ICON)))
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.resize(708, 720)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 12)
        root.setSpacing(0)

        header = DraggableHeader()
        header.setObjectName("settingsHeader")
        header.setFixedHeight(56)
        header_layout = QGridLayout(header)
        header_layout.setContentsMargins(12, 4, 12, 0)
        header_layout.setColumnStretch(0, 1)
        header_layout.setColumnStretch(2, 1)
        logo = QWidget()
        logo_layout = QHBoxLayout(logo)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setSpacing(4)
        mark = ScalableIconLabel(QIcon(str(APP_ICON)), QSize(24, 24))
        logo_layout.addWidget(mark)
        brand = QLabel(APP_NAME)
        brand.setObjectName("settingsBrand")
        logo_layout.addWidget(brand)
        header_layout.addWidget(logo, 0, 1, Qt.AlignmentFlag.AlignCenter)
        controls = QHBoxLayout()
        controls.setSpacing(12)
        minimize = QPushButton("−")
        minimize.setObjectName("windowControl")
        minimize.setFixedSize(32, 28)
        minimize.clicked.connect(self.showMinimized)
        close = QPushButton("×")
        close.setObjectName("windowControl")
        close.setFixedSize(32, 28)
        close.clicked.connect(self.reject)
        controls.addWidget(minimize)
        controls.addWidget(close)
        header_layout.addLayout(controls, 0, 2, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        root.addWidget(header)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(8, 0, 8, 0)
        body_layout.setSpacing(6)
        self.tabs = SettingsTabWidget()
        body_layout.addWidget(self.tabs, 1)

        general_tab = QWidget()
        general_tab.setObjectName("settingsPage")
        general_layout = QVBoxLayout(general_tab)
        general_layout.setContentsMargins(22, 18, 22, 18)
        general_layout.setSpacing(0)
        general_layout.addWidget(ProfileSectionHeading(tr("Startup")))
        general_layout.addSpacing(SECTION_CONTENT_GAP)
        self.startup_checkbox = QCheckBox(tr("Launch at startup"))
        self.startup_checkbox.setObjectName("startupEnabled")
        self.startup_checkbox.setChecked(settings.startup_enabled)
        self.minimized_checkbox = QCheckBox(tr("Minimized to the taskbar"))
        self.minimized_checkbox.setObjectName("startMinimized")
        self.minimized_checkbox.setChecked(settings.start_minimized)
        minimized_option = QWidget()
        minimized_option.setObjectName("minimizedOption")
        minimized_layout = QHBoxLayout(minimized_option)
        minimized_layout.setContentsMargins(22, CONTROL_ROW_GAP, 0, 0)
        minimized_layout.addWidget(self.minimized_checkbox)
        minimized_option.setVisible(self.startup_checkbox.isChecked())
        self.startup_checkbox.toggled.connect(minimized_option.setVisible)
        general_layout.addWidget(self.startup_checkbox)
        general_layout.addWidget(minimized_option)
        general_layout.addSpacing(20)
        general_layout.addWidget(ProfileSectionHeading(tr("Profiles")))
        general_layout.addSpacing(SECTION_CONTENT_GAP)
        default_profile_form = QFormLayout()
        self.default_profile_picker = QComboBox()
        self.default_profile_picker.setObjectName("defaultAssignedProfile")
        self.default_profile_picker.addItems(self.profiles)
        self.default_profile_picker.setCurrentText(settings.default_profile)
        default_profile_form.setContentsMargins(8, 0, 0, 0)
        default_profile_form.setHorizontalSpacing(16)
        default_profile_form.addRow(
            tr("Default assigned profile"), self.default_profile_picker)
        general_layout.addLayout(default_profile_form)
        general_layout.addSpacing(20)
        general_layout.addWidget(ProfileSectionHeading(tr("Game mode")))
        general_layout.addSpacing(SECTION_CONTENT_GAP)
        self.game_auto_checkbox = QCheckBox(tr("Automatic for full-screen applications"))
        self.game_auto_checkbox.setObjectName("gameModeAuto")
        self.game_auto_checkbox.setToolTip(
            tr("In game mode, pawz stops sending input and leaves the controller to the game. "
               "Browsers and video players never switch to it. "
               "MINUS + PLUS toggles game mode by hand."))
        self.game_auto_checkbox.setChecked(settings.game_mode_auto)
        general_layout.addWidget(self.game_auto_checkbox)
        general_layout.addSpacing(CONTROL_ROW_GAP)
        game_lists = QFormLayout()
        game_lists.setContentsMargins(8, 0, 0, 0)
        game_lists.setHorizontalSpacing(16)
        self.games_edit = QLineEdit(", ".join(settings.games))
        self.games_edit.setObjectName("gamesList")
        self.games_edit.setPlaceholderText(tr("game.exe, other-game.exe"))
        self.non_games_edit = QLineEdit(", ".join(settings.non_games))
        self.non_games_edit.setObjectName("nonGamesList")
        self.non_games_edit.setPlaceholderText(tr("full-screen-app.exe"))
        game_lists.addRow(tr("Always in game mode"), self.games_edit)
        game_lists.addRow(tr("Never in game mode"), self.non_games_edit)
        general_layout.addLayout(game_lists)
        general_layout.addSpacing(20)
        general_layout.addWidget(ProfileSectionHeading(tr("Debug")))
        general_layout.addSpacing(SECTION_CONTENT_GAP)
        self.debug_startup_checkbox = QCheckBox(tr("Open the debug window at startup"))
        self.debug_startup_checkbox.setObjectName("debugWindowOnStartup")
        self.debug_startup_checkbox.setChecked(settings.debug_window_on_startup)
        general_layout.addWidget(self.debug_startup_checkbox)
        self.debug_button = QPushButton(tr("Debug Window"))
        self.debug_button.setObjectName("openDebugWindow")
        self.debug_button.clicked.connect(self.open_debug_window)
        general_layout.addSpacing(CONTROL_ROW_GAP)
        general_layout.addWidget(self.debug_button)
        general_layout.addStretch()
        self.tabs.addTab(general_tab, tr("GENERAL"))
        self.tabs.addTab(self._display_tab(settings), tr("DISPLAY"))

        profiles_tab = QWidget()
        profiles_tab.setObjectName("settingsPage")
        profiles_layout = QVBoxLayout(profiles_tab)
        profiles_layout.setContentsMargins(14, 14, 14, 12)
        profiles_layout.setSpacing(8)
        profile_actions = QWidget()
        profile_actions_layout = QVBoxLayout(profile_actions)
        profile_actions_layout.setContentsMargins(14, 16, 14, 14)
        profile_actions_layout.setSpacing(18)
        self.add_profile_button = QPushButton(tr("Add a profile..."))
        self.add_profile_button.setObjectName("settingsAction")
        self.add_profile_button.clicked.connect(self.add_profile)
        profile_actions_layout.addWidget(
            self.add_profile_button, 0, Qt.AlignmentFlag.AlignCenter)
        profile_separator = QFrame()
        profile_separator.setObjectName("addProfileSeparator")
        profile_separator.setFixedHeight(1)
        profile_actions_layout.addWidget(profile_separator)
        profiles_layout.addWidget(profile_actions)
        self.profile_picker = QComboBox()
        self.profile_picker.setObjectName("settingsProfilePicker")
        self.profile_picker.addItems(self.profiles)
        profile_selectors = QGridLayout()
        profile_selectors.setContentsMargins(14, 0, 0, 0)
        profile_selectors.setHorizontalSpacing(8)
        profile_selectors.setVerticalSpacing(8)
        profile_selectors.setColumnStretch(1, 1)
        profile_label = QLabel(tr("Profile"))
        profile_label.setObjectName("profilePickerLabel")
        profile_label.setBuddy(self.profile_picker)
        profile_selectors.addWidget(profile_label, 0, 0, Qt.AlignmentFlag.AlignLeft)
        profile_selectors.addWidget(self.profile_picker, 0, 1)
        action_column = 2
        for title, name, callback in (
                (tr("Duplicate"), "duplicateProfile", self.duplicate_profile),
                (tr("Rename"), "renameProfile", self.rename_profile),
                (tr("Delete"), "deleteProfile", self.delete_profile)):
            button = profile_action_button(title, {
                "duplicateProfile": "duplicate", "renameProfile": "edit", "deleteProfile": "delete"
            }[name])
            button.setObjectName(name)
            button.clicked.connect(callback)
            profile_selectors.addWidget(button, 0, action_column)
            action_column += 1
            if name == "deleteProfile":
                self.delete_profile_button = button
        self.display_model_picker = QComboBox()
        self.display_model_picker.setObjectName("displayControllerModel")
        for model in self.catalog.definitions:
            self.display_model_picker.addItem(model_name(model), model.id)
        self.display_model_picker.setCurrentIndex(max(0, self.display_model_picker.findData(settings.display_controller_model)))
        self.display_model_picker.currentIndexChanged.connect(self.change_display_model)
        display_label = QLabel(tr("Show buttons of"))
        display_label.setObjectName("displayControllerLabel")
        display_label.setBuddy(self.display_model_picker)
        profile_selectors.addWidget(display_label, 1, 0, Qt.AlignmentFlag.AlignLeft)
        profile_selectors.addWidget(self.display_model_picker, 1, 1)
        self.display_model_preview = SvgView()
        self.display_model_preview.setObjectName("displayModelPreview")
        # Beside its picker, under the profile action buttons, centred on the row.
        self.display_model_preview.setFixedSize(3 * 34 + 2 * profile_selectors.horizontalSpacing(), 64)
        profile_selectors.addWidget(self.display_model_preview, 1, 2, 1, 3, Qt.AlignmentFlag.AlignCenter)
        self._update_display_model_preview()
        profiles_layout.addLayout(profile_selectors)
        self.profile_editor_host = QWidget()
        self.profile_editor_host.setObjectName("profileEditorHost")
        self.profile_editor_layout = QVBoxLayout(self.profile_editor_host)
        self.profile_editor_layout.setContentsMargins(0, 0, 0, 0)
        profiles_layout.addWidget(self.profile_editor_host, 1)
        self.profile_picker.currentIndexChanged.connect(self._select_profile)
        self.tabs.addTab(profiles_tab, tr("PROFILES"))
        self.controllers_page = ControllersPage(settings, self.catalog, controller_manager)
        self.controllers_page.catalog_changed.connect(self._reload_display_models)
        self.tabs.addTab(self.controllers_page, tr("CONTROLLERS"))
        self._select_profile(self.profile_picker.currentIndex())
        if initial_tab is not None:
            tab_index = self.tabs.indexOf(
                profiles_tab if initial_tab == "profiles" else general_tab)
            self.tabs.setCurrentIndex(tab_index)

        footer_actions = QWidget()
        footer_actions.setObjectName("settingsFooterActions")
        buttons = QHBoxLayout(footer_actions)
        buttons.setContentsMargins(18, 12, 18, 12)
        buttons.setSpacing(8)
        self.save_button = QPushButton(tr("Save"))
        self.save_button.setObjectName("settingsFooter")
        self.close_button = QPushButton(tr("Close"))
        self.close_button.setObjectName("settingsFooter")
        self.close_button.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.close_button)
        buttons.addStretch()
        body_layout.addWidget(footer_actions)
        root.addWidget(body, 1)
        self.setStyleSheet(stylesheet())
        self.save_button.clicked.connect(self._accept_settings)

    def _display_tab(self, settings) -> QWidget:
        """Language and theme: both apply when pawz restarts."""
        tab = QWidget()
        tab.setObjectName("settingsPage")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(0)
        self.language_picker = QComboBox()
        self.language_picker.setObjectName("languagePicker")
        self.language_picker.addItem(tr("Automatic (Windows language)"), AUTO)
        for code, name in LANGUAGES.items():
            self.language_picker.addItem(name, code)
        self.language_picker.setCurrentIndex(
            max(0, self.language_picker.findData(settings.language)))
        self.theme_picker = QComboBox()
        self.theme_picker.setObjectName("themePicker")
        for theme in THEMES.values():
            self.theme_picker.addItem(tr(theme.name), theme.id)
        self.theme_picker.setCurrentIndex(max(0, self.theme_picker.findData(settings.theme)))
        self.controller_style_picker = QComboBox()
        self.controller_style_picker.setObjectName("controllerStylePicker")
        for style, name in artwork_styles.STYLES.items():
            self.controller_style_picker.addItem(tr(name), style)
        self.controller_style_picker.setCurrentIndex(
            max(0, self.controller_style_picker.findData(settings.controller_style)))
        self._initial_controller_style = artwork_styles.current()
        self.controller_style_picker.currentIndexChanged.connect(self._preview_controller_style)
        for index, (heading, rows) in enumerate((
                (tr("Language"), ((tr("Interface language"), self.language_picker),)),
                (tr("Theme"), ((tr("Color scheme"), self.theme_picker),
                               (tr("Controller style"), self.controller_style_picker))))):
            if index:
                layout.addSpacing(20)
            layout.addWidget(ProfileSectionHeading(heading))
            layout.addSpacing(SECTION_CONTENT_GAP)
            form = QFormLayout()
            form.setContentsMargins(8, 0, 0, 0)
            form.setHorizontalSpacing(16)
            form.setVerticalSpacing(CONTROL_ROW_GAP)
            for label, picker in rows:
                picker_label = QLabel(label)
                picker_label.setMinimumWidth(140)
                form.addRow(picker_label, picker)
            layout.addLayout(form)
        layout.addSpacing(20)
        self.display_note = QLabel(tr("Language and theme changes apply when pawz restarts."))
        self.display_note.setObjectName("displayNote")
        self.display_note.setWordWrap(True)
        self.display_note.setContentsMargins(8, 0, 0, 0)
        self.display_note.setVisible(False)
        for picker in (self.language_picker, self.theme_picker):
            picker.currentIndexChanged.connect(self._update_display_note)
        layout.addWidget(self.display_note)
        layout.addStretch()
        return tab

    def _preview_controller_style(self, *_):
        """Controller drawings follow the chosen style at once (restored on cancel)."""
        artwork_styles.set_current(self.controller_style_picker.currentData())
        self._update_display_model_preview()
        self.controllers_page.refresh()

    def display_changed(self) -> bool:
        """Whether the chosen language or theme differs from the running one."""
        return (self.language_picker.currentData() != self.settings.language
                or self.theme_picker.currentData() != self.settings.theme)

    def _update_display_note(self, *_):
        self.display_note.setVisible(self.display_changed())

    def open_debug_window(self):
        if self.debug_window is None:
            self.debug_window = DebugWindow()
        self.debug_window.showNormal()
        self.debug_window.raise_()
        self.debug_window.activateWindow()

    def _accept_settings(self):
        self._cancel_active_capture()
        if self.current_profile_name is not None and self.profile_editor is not None:
            self.profiles[self.current_profile_name] = self.profile_editor.profile
        self.accept()

    def _select_profile(self, index: int):
        if self.current_profile_name is not None and self.profile_editor is not None:
            self.profile_editor.cancel_capture()
            self.profiles[self.current_profile_name] = self.profile_editor.profile
            self.profile_editor_layout.removeWidget(self.profile_editor)
            self.profile_editor.deleteLater()
            self.profile_editor = None
        if index < 0:
            self.current_profile_name = None
            return
        name = self.profile_picker.itemText(index)
        self.current_profile_name = name
        self.delete_profile_button.setEnabled(self.profiles[name].profile_id != SYSTEM_DEFAULT_PROFILE_ID)
        self.profile_editor = ProfileEditor(
            self.profiles[name], self.profile_editor_host, self.controller_manager,
            self.catalog.get(self.display_model_picker.currentData()))
        self.profile_editor_layout.addWidget(self.profile_editor)

    def add_profile(self):
        if self.current_profile_name is not None and self.profile_editor is not None:
            self.profile_editor.cancel_capture()
            self.profiles[self.current_profile_name] = self.profile_editor.profile
        dialog = ProfileCreationDialog(list(self.profiles), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name = dialog.profile_name
        if name in self.profiles:
            QMessageBox.warning(self, tr("Profile exists"), tr("A profile already has this name."))
            return
        profile = copy.deepcopy(self.profiles[dialog.model_name])
        profile.name = name
        profile.profile_id = str(uuid4())
        self.profiles[name] = profile
        self.profile_picker.addItem(name)
        self.default_profile_picker.addItem(name)
        self.profile_picker.setCurrentIndex(self.profile_picker.count() - 1)

    def change_display_model(self, *_):
        self.settings.display_controller_model = self.display_model_picker.currentData()
        self._update_display_model_preview()
        if self.profile_editor:
            self.profile_editor.display_model = self.catalog.get(self.settings.display_controller_model)
            self.profile_editor.draw()

    def _update_display_model_preview(self):
        """Show the controller whose buttons the shortcuts are drawn with."""
        try:
            model = self.catalog.get(self.display_model_picker.currentData())
        except KeyError:
            model = None
        artwork = resolve_artwork(model) if model else None
        self.display_model_preview.set_path(artwork)
        self.display_model_preview.setToolTip(model_name(model) if model else "")

    def _reload_display_models(self):
        selected = self.display_model_picker.currentData()
        self.display_model_picker.blockSignals(True)
        self.display_model_picker.clear()
        for model in self.catalog.definitions:
            self.display_model_picker.addItem(model_name(model), model.id)
        self.display_model_picker.setCurrentIndex(max(0, self.display_model_picker.findData(selected)))
        self.display_model_picker.blockSignals(False)
        self.change_display_model()

    def _store_profile(self):
        if self.profile_editor and self.current_profile_name:
            self.profiles[self.current_profile_name] = self.profile_editor.profile
        self.settings.default_profile = self.default_profile_picker.currentText()

    def _reload_profiles(self, selected):
        self.current_profile_name = None
        if self.profile_editor:
            self.profile_editor_layout.removeWidget(self.profile_editor)
            self.profile_editor.deleteLater()
            self.profile_editor = None
        self.profile_picker.blockSignals(True)
        self.profile_picker.clear()
        self.profile_picker.addItems(self.profiles)
        self.profile_picker.setCurrentText(selected)
        self.profile_picker.blockSignals(False)
        self.default_profile_picker.clear()
        self.default_profile_picker.addItems(self.profiles)
        self.default_profile_picker.setCurrentText(self.settings.default_profile)
        self._select_profile(self.profile_picker.currentIndex())

    def duplicate_profile(self):
        self._store_profile()
        name, ok = QInputDialog.getText(self, tr("Duplicate"), tr("Profile name"))
        if ok:
            try:
                self.settings.duplicate_profile(self.current_profile_name, name.strip())
                self._reload_profiles(name.strip())
            except ValueError as exc:
                QMessageBox.warning(self, tr("Invalid profile"), tr(str(exc)))

    def rename_profile(self):
        self._store_profile()
        name, ok = QInputDialog.getText(
            self, tr("Rename"), tr("Profile name"), text=self.current_profile_name)
        if ok and name.strip() != self.current_profile_name:
            try:
                self.settings.rename_profile(self.current_profile_name, name.strip())
                self._reload_profiles(name.strip())
            except ValueError as exc:
                QMessageBox.warning(self, tr("Invalid profile"), tr(str(exc)))

    def delete_profile(self):
        self._store_profile()
        try:
            self.settings.remove_profile(self.current_profile_name)
            self._reload_profiles(self.settings.default_profile)
        except ValueError as exc:
            QMessageBox.warning(self, tr("Protected profile"), tr(str(exc)))

    def _cancel_active_capture(self):
        if self.profile_editor is not None:
            self.profile_editor.cancel_capture()

    def reject(self):
        self._cancel_active_capture()
        artwork_styles.set_current(self._initial_controller_style)
        super().reject()

    def closeEvent(self, event):
        self._cancel_active_capture()
        super().closeEvent(event)


class DraggableHeader(QWidget):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None:
                handle.startSystemMove()
        super().mousePressEvent(event)


class ControllerArtwork(QWidget):
    CROWN_SPACE = 12  # reserved above the drawing so the crown stays inside the widget
    # Crown outline around (0, 0) = middle of its base, in pixels.
    CROWN = ((-9, -9), (-5, -5), (0, -13), (5, -5), (9, -9), (7, 0), (-7, 0))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.connected = False
        self.primary = False
        self.svg_renderer = None
        self._top_edge: tuple[tuple, tuple[float, QColor]] | None = None
        self.crown_rect = QRectF()
        self.setMouseTracking(True)

    def set_illustration(self, path):
        if self.svg_renderer:
            self.svg_renderer.deleteLater()
        self.svg_renderer = renderer_for(path, self) if path else None
        self._top_edge = None
        self.update()

    def artwork_rect(self) -> QRectF:
        size = self.svg_renderer.defaultSize()
        size.scale(self.width(), self.height() - self.CROWN_SPACE, Qt.AspectRatioMode.KeepAspectRatio)
        return QRectF((self.width() - size.width()) / 2,
                      self.CROWN_SPACE + (self.height() - self.CROWN_SPACE - size.height()) / 2,
                      size.width(), size.height())

    def top_edge(self, rect: QRectF) -> tuple[float, QColor]:
        """Where the drawing's outline crosses the vertical centre line, and its colour."""
        key = (rect.width(), rect.height())
        if self._top_edge is None or self._top_edge[0] != key:
            image = QImage(max(1, round(rect.width())), max(1, round(rect.height())),
                           QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            self.svg_renderer.render(painter, QRectF(0, 0, image.width(), image.height()))
            painter.end()
            x = image.width() // 2
            y = next((row for row in range(image.height()) if image.pixelColor(x, row).alpha() > 128),
                     0)
            color = QColor(image.pixelColor(x, y))
            color.setAlpha(255)
            self._top_edge = (key, (y, color))
        return self._top_edge[1]

    def paint_crown(self, painter: QPainter, rect: QRectF):
        """The crown stands on the drawing's top line, outlined like that line."""
        top, color = self.top_edge(rect)
        line = max(1.0, artwork_styles.OUTLINE_WIDTH * max(rect.width(), rect.height()))
        base = QPoint(round(rect.center().x()), round(rect.top() + top + line / 2))
        crown = QPainterPath()
        crown.moveTo(base.x() + self.CROWN[0][0], base.y() + self.CROWN[0][1])
        for dx, dy in self.CROWN[1:]:
            crown.lineTo(base.x() + dx, base.y() + dy)
        crown.closeSubpath()
        painter.setPen(QPen(color, line, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(QColor("#f9c74f"))
        painter.drawPath(crown)
        self.crown_rect = crown.boundingRect().adjusted(-2, -2, 2, 2)

    def set_state(self, connected: bool, primary: bool):
        self.connected = connected
        self.primary = primary
        if not connected or not primary:
            QToolTip.hideText()
        self.update()

    def mouseMoveEvent(self, event):
        if self.svg_renderer and self.svg_renderer.isValid():
            crown_area = self.crown_rect
        else:
            scale = min((self.width() - 18) / 160, (self.height() - 25) / 116)
            origin_x = (self.width() - 160 * scale) / 2
            crown_area = QRectF(origin_x + 66.5 * scale, 18 - 3 * scale,
                                26 * scale, 25 * scale)
        if self.connected and self.primary and crown_area.contains(event.position()):
            QToolTip.showText(
                event.globalPosition().toPoint(), tr("Primary controller"), self)
        else:
            QToolTip.hideText()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        QToolTip.hideText()
        super().leaveEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.svg_renderer and self.svg_renderer.isValid():
            rect = self.artwork_rect()
            painter.setOpacity(1.0 if self.connected else 0.2)
            self.svg_renderer.render(painter, rect)
            if self.connected and self.primary:
                self.paint_crown(painter, rect)
            return
        scale = min((self.width() - 18) / 160, (self.height() - 25) / 116)
        painter.translate((self.width() - 160 * scale) / 2, 18)
        painter.scale(scale, scale)
        painter.setOpacity(1.0 if self.connected else 0.13)

        body = QPainterPath()
        body.moveTo(34, 13)
        body.cubicTo(24, 13, 17, 20, 14, 32)
        body.lineTo(2, 76)
        body.cubicTo(-1, 91, 6, 103, 16, 102)
        body.cubicTo(22, 101, 33, 88, 43, 78)
        body.cubicTo(47, 74, 52, 72, 59, 72)
        body.lineTo(101, 72)
        body.cubicTo(108, 72, 113, 75, 118, 80)
        body.lineTo(141, 102)
        body.cubicTo(151, 108, 160, 98, 158, 81)
        body.lineTo(146, 33)
        body.cubicTo(143, 20, 136, 13, 126, 13)
        body.cubicTo(117, 13, 111, 19, 103, 19)
        body.lineTo(57, 19)
        body.cubicTo(49, 19, 42, 13, 34, 13)
        body.closeSubpath()
        painter.setPen(QPen(QColor("#07090d"), 7, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(QColor("#55565b"))
        painter.drawPath(body)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#898b8e"))
        painter.drawRoundedRect(48, 47, 6, 20, 2, 2)
        painter.drawRoundedRect(41, 54, 20, 6, 2, 2)
        painter.drawEllipse(35, 36, 13, 13)
        painter.drawEllipse(79, 57, 15, 15)
        painter.setBrush(QColor("#ededed"))
        painter.drawEllipse(69, 34, 9, 9)

        for x, y, color in (
            (112, 33, "#ffd22e"),
            (122, 42, "#ed4b48"),
            (112, 52, "#10c96b"),
            (102, 42, "#39a9ed"),
        ):
            painter.setBrush(QColor(color))
            painter.drawEllipse(x, y, 7, 7)
        if self.connected and self.primary:
            crown = QPainterPath()
            painter.save()
            painter.translate(-9.5, -7)
            crown.moveTo(76, 24)
            crown.lineTo(73, 8)
            crown.lineTo(82, 15)
            crown.lineTo(89, 4)
            crown.lineTo(97, 15)
            crown.lineTo(105, 8)
            crown.lineTo(102, 24)
            crown.closeSubpath()
            painter.setPen(QPen(QColor("#8b6000"), 1.5))
            painter.setBrush(QColor("#ffd54a"))
            painter.drawPath(crown)
            painter.drawRoundedRect(76, 24, 26, 5, 1, 1)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#ec514b"))
            painter.drawEllipse(87, 16, 4, 4)
            painter.setBrush(QColor("#39a9ed"))
            painter.drawEllipse(78, 18, 3, 3)
            painter.drawEllipse(97, 18, 3, 3)
            painter.restore()


class ControllerSlot(QWidget):
    profile_changed = Signal(str, str)
    set_primary_requested = Signal(str)
    forget_requested = Signal(str)
    WIDTH = 140

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("controllerSlot")
        self.device_key = ""
        self.setFixedWidth(self.WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.artwork = ControllerArtwork()
        self.artwork.setFixedSize(126, 97)
        layout.addWidget(self.artwork, 0, Qt.AlignmentFlag.AlignHCenter)

        self.name = QLabel()
        self.name.setObjectName("controllerName")
        self.name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name.setWordWrap(True)
        self.name.setMinimumHeight(19)
        layout.addWidget(self.name)

        self.forget_button = QPushButton(tr("Forget"))
        self.forget_button.setObjectName("forgetController")
        self.forget_button.setFixedSize(59, 21)
        self.forget_button.clicked.connect(self._request_forget)
        layout.addWidget(self.forget_button, 0, Qt.AlignmentFlag.AlignHCenter)

        self.battery = QLabel()
        self.battery.setObjectName("batteryLabel")
        self.battery.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.battery.setFixedHeight(15)
        layout.addWidget(self.battery)

        self.battery_bar = QProgressBar()
        self.battery_bar.setTextVisible(False)
        self.battery_bar.setFixedSize(78, 5)
        self.battery_bar.valueChanged.connect(self._update_battery_color)
        self._connected = False
        self._battery_known = False
        self._battery_target: int | None = None
        self.battery_animation = QPropertyAnimation(self.battery_bar, b"value", self)
        self.battery_animation.setDuration(1400)
        layout.addWidget(self.battery_bar, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(6)

        self.profile_picker = QComboBox()
        self.profile_picker.setObjectName("profilePicker")
        self.profile_picker.setFixedWidth(126)
        self.profile_picker.view().setStyleSheet(themed(
            "QListView { color:#f5f7fb; background:#1b355b; "
            "selection-color:#ffffff; selection-background-color:#2765cc; }"))
        self.profile_picker.currentIndexChanged.connect(self._profile_selected)
        layout.addWidget(self.profile_picker, 0, Qt.AlignmentFlag.AlignHCenter)

        self.set_primary = QPushButton(tr("SET PRIMARY"))
        self.set_primary.setObjectName("setPrimary")
        self.set_primary.setFixedSize(95, 25)
        self.set_primary.clicked.connect(self._request_primary)
        layout.addWidget(self.set_primary, 0, Qt.AlignmentFlag.AlignHCenter)

    def configure(self, key: str | None, name: str, connected: bool,
                  power_level: str, profiles: list[str], assigned: str | None,
                  primary: bool, connected_count: int):
        newly_connected = connected and not self._connected
        self._connected = connected
        self.device_key = key or ""
        self.artwork.set_state(connected, primary)
        self.name.setText(name)
        self.name.setProperty("connected", connected)
        self.name.style().unpolish(self.name)
        self.name.style().polish(self.name)
        self.battery.setVisible(connected)
        self.battery_bar.setVisible(connected)
        self.forget_button.setVisible(not connected)
        self.profile_picker.setVisible(connected)
        self.set_primary.setVisible(connected and connected_count > 1 and not primary)
        if connected:
            self.update_battery(power_level, animate=newly_connected)
            self.profile_picker.blockSignals(True)
            self.profile_picker.clear()
            for profile in profiles:
                self.profile_picker.addItem(profile, profile)
            index = self.profile_picker.findData(assigned or profiles[0])
            self.profile_picker.setCurrentIndex(max(index, 0))
            self.profile_picker.blockSignals(False)
        else:
            self.battery_animation.stop()
            self._battery_target = None
            self._battery_known = False
            self.battery_bar.setValue(0)

    def update_battery(self, power_level: str, animate: bool = False):
        was_known = self._battery_known
        if power_level == "wired":
            label, percentage = tr("Wired"), 100
        else:
            percentage = battery_percentage(power_level)
            if percentage is None:
                label = "—"
            else:
                label = f"{percentage}%" if power_level in ("empty", "full", "max") else f"~{percentage}%"
        self.battery.setText(label)
        target = percentage or 0
        self._battery_known = percentage is not None
        if animate or (percentage is not None and not was_known):
            self.battery_animation.stop()
            self._battery_target = target
            self.battery_bar.setValue(0)
            self.battery_animation.setStartValue(0)
            self.battery_animation.setEndValue(target)
            self.battery_animation.start()
        elif self.battery_animation.state() != QPropertyAnimation.State.Running:
            self._battery_target = target
            self.battery_bar.setValue(target)
        elif target != self._battery_target:
            self.battery_animation.stop()
            self._battery_target = target
            self.battery_bar.setValue(target)

    def _update_battery_color(self, value: int):
        if not self._battery_known:
            color = "#7587a3"
        else:
            color = "#00c96b" if value >= 80 else "#ffc21c" if value >= 50 else "#f26945"
        self.battery_bar.setStyleSheet(themed(
            f"QProgressBar {{ background:#17345e; border:0; border-radius:3px; }}"
            f"QProgressBar::chunk {{ background:{color}; border-radius:3px; }}"))

    def _profile_selected(self, index: int):
        if self.device_key and index >= 0:
            self.profile_changed.emit(self.device_key, str(self.profile_picker.currentData() or ""))

    def _request_primary(self):
        if self.device_key:
            self.set_primary_requested.emit(self.device_key)

    def _request_forget(self):
        if self.device_key:
            self.forget_requested.emit(self.device_key)


class MainWindow(QMainWindow):
    def __init__(self, settings, manager):
        super().__init__()
        load_fonts()
        self.settings, self.manager = settings, manager
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(APP_ICON)))
        self.debug_window = DebugWindow()
        self.setMinimumSize(672, 420)
        self.resize(770, 440)
        surface = QWidget()
        surface.setObjectName("mainSurface")
        self.setCentralWidget(surface)
        root = QVBoxLayout(surface)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = DraggableHeader()
        header.setFixedHeight(112)
        header_layout = QGridLayout(header)
        header_layout.setContentsMargins(20, 10, 20, 0)
        header_layout.setColumnStretch(0, 1)
        header_layout.setColumnStretch(2, 1)
        # The logo spells the name: no text next to it on the main window.
        mark = ScalableIconLabel(QIcon(str(APP_ICON)), QSize(96, 96))
        mark.setObjectName("brandIcon")
        mark.setAccessibleName(APP_NAME)
        # Spans every column so it is centred on the window, not between the controls.
        header_layout.addWidget(mark, 0, 0, 1, 3, Qt.AlignmentFlag.AlignCenter)
        controls = QHBoxLayout()
        controls.setSpacing(16)
        minimize = QPushButton("−")
        minimize.setObjectName("windowControl")
        minimize.setFixedSize(34, 30)
        minimize.clicked.connect(self.showMinimized)
        close = QPushButton("×")
        close.setObjectName("windowControl")
        close.setFixedSize(34, 30)
        close.clicked.connect(self.close)
        controls.addWidget(minimize)
        controls.addWidget(close)
        header_layout.addLayout(controls, 0, 2, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        root.addWidget(header)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(10, 16, 10, 4)
        body_layout.setSpacing(0)

        self.previous_controllers = self._controller_nav_button("‹")
        self.previous_controllers[1].clicked.connect(lambda: self._scroll_controllers(-1))
        body_layout.addWidget(self.previous_controllers[0], 0, Qt.AlignmentFlag.AlignVCenter)

        self.controller_scroll = QScrollArea()
        self.controller_scroll.setObjectName("controllerScroll")
        self.controller_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.controller_scroll.viewport().setAutoFillBackground(False)
        self.controller_scroll.setWidgetResizable(False)
        self.controller_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.controller_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.controller_scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.controller_content = QWidget()
        self.controller_content_layout = QHBoxLayout(self.controller_content)
        self.controller_content_layout.setContentsMargins(0, 0, 0, 0)
        self.controller_content_layout.setSpacing(0)
        self.controller_content_layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
        self.controller_scroll.setWidget(self.controller_content)
        body_layout.addWidget(self.controller_scroll, 1)

        self.next_controllers = self._controller_nav_button("›")
        self.next_controllers[1].clicked.connect(lambda: self._scroll_controllers(1))
        body_layout.addWidget(self.next_controllers[0], 0, Qt.AlignmentFlag.AlignVCenter)
        self.slots = []
        body_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        horizontal_scroll = self.controller_scroll.horizontalScrollBar()
        horizontal_scroll.valueChanged.connect(self._update_controller_navigation)
        horizontal_scroll.rangeChanged.connect(self._update_controller_navigation)
        self.previous_controllers[1].hide()
        self.next_controllers[1].hide()
        root.addWidget(body, 1)

        separator = QFrame()
        separator.setObjectName("separator")
        separator.setFixedHeight(1)
        separator_layout = QHBoxLayout()
        separator_layout.setContentsMargins(22, 0, 22, 0)
        separator_layout.addWidget(separator)
        root.addLayout(separator_layout)

        footer = QWidget()
        footer.setObjectName("bottomButtonBar")
        footer.setFixedHeight(83)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 19, 0, 19)
        footer_layout.setSpacing(27)
        footer_layout.addStretch()
        manage = QPushButton(tr("Manage profiles"))
        manage.setObjectName("primaryAction")
        manage.setFixedSize(196, 36)
        manage.setIcon(action_icon("profiles"))
        manage.setIconSize(QSize(17, 17))
        manage.clicked.connect(self.manage_profiles)
        settings_button = QPushButton(tr("Settings"))
        settings_button.setObjectName("primaryAction")
        settings_button.setFixedSize(196, 36)
        settings_button.setIcon(action_icon("settings"))
        settings_button.setIconSize(QSize(17, 17))
        settings_button.clicked.connect(lambda: self.open_settings())
        footer_layout.addWidget(manage)
        footer_layout.addWidget(settings_button)
        footer_layout.addStretch()
        root.addWidget(footer)

        self._known_snapshot = None
        self._primary_snapshot = None
        self.manager.devices_changed.connect(self.refresh)
        self._battery_timer = QTimer(self)
        self._battery_timer.setInterval(1000)
        self._battery_timer.timeout.connect(self.refresh_battery)
        self._battery_timer.start()
        self.refresh()

        app = QApplication.instance()
        if app is None:
            raise RuntimeError("MainWindow requires a running QApplication")
        if isinstance(app, QApplication):
            app.setWindowIcon(QIcon(str(APP_ICON)))
        self.tray = QSystemTrayIcon(QIcon(str(APP_ICON)), self)
        menu = QMenu()
        menu.setObjectName("trayMenu")
        menu.setStyleSheet(stylesheet())
        menu.addAction(tr("Configuration"), self.show_from_tray)
        menu.addAction(tr("Quit"), app.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.setToolTip(APP_NAME)
        game_mode_changed = getattr(self.manager, "game_mode_changed", None)
        if game_mode_changed is not None:
            game_mode_changed.connect(
                lambda active: self.tray.setToolTip(
                    tr("{app} — game mode").format(app=APP_NAME) if active else APP_NAME))
        self.tray.show()

    def refresh(self, *_):
        connected = list(self.manager.controllers)
        if connected and self.settings.primary_device not in connected:
            self.settings.primary_device = connected[0]
        known_before = dict(self.settings.known_devices)
        for key in connected:
            self.settings.known_devices.setdefault(key, getattr(self.manager.controllers[key], "name", key))

        disconnected = [
            (key, name) for key, name in self.settings.known_devices.items()
            if key not in self.manager.controllers
        ]
        entries = [
            (key, self.settings.known_devices.get(
                key, getattr(self.manager.controllers[key], "name", key)), True)
            for key in connected
        ]
        entries.extend((key, name, False) for key, name in disconnected)

        while len(self.slots) > len(entries):
            slot = self.slots.pop()
            self.controller_content_layout.removeWidget(slot)
            slot.deleteLater()
        while len(self.slots) < len(entries):
            slot = ControllerSlot()
            slot.profile_changed.connect(self.profile_selected)
            slot.set_primary_requested.connect(self.set_primary)
            slot.forget_requested.connect(self.forget_device)
            self.slots.append(slot)
            self.controller_content_layout.addWidget(slot)

        profile_names = list(self.settings.profiles)
        connected_count = len(connected)
        catalog = ControllerCatalog(DATA_DIR / "controllers" / "catalog.json")
        for slot, (key, name, is_connected) in zip(self.slots, entries):
            preferences = self.settings.device_preferences.get(key, {})
            model_id = resolve_model(catalog.definitions, preferences.get("guid", ""), name,
                                     preferences.get("model_id"))
            slot.artwork.set_illustration(resolve_artwork(catalog.get(model_id), preferences.get("svg")))
            name = preferences.get("name") or name
            power = self.manager.power_levels.get(key, "unknown") if key else "unknown"
            assigned = self.settings.assignments.get(key, self.settings.default_profile) if key else None
            slot.configure(
                key, name, is_connected, power, profile_names, assigned,
                key == self.settings.primary_device, connected_count)

        self.controller_content.adjustSize()
        self.controller_content.updateGeometry()
        QTimer.singleShot(0, self._update_controller_navigation)

        if (self._known_snapshot != self.settings.known_devices
                or self._primary_snapshot != self.settings.primary_device):
            save(self.settings)
            self._known_snapshot = dict(self.settings.known_devices)
            self._primary_snapshot = self.settings.primary_device
        elif known_before != self.settings.known_devices:
            save(self.settings)

    @staticmethod
    def _controller_nav_button(label: str) -> tuple[QWidget, QPushButton]:
        container = QWidget()
        container.setFixedWidth(30)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        button = QPushButton(label)
        button.setObjectName("windowControl")
        button.setFixedSize(27, 41)
        layout.addWidget(button, 0, Qt.AlignmentFlag.AlignCenter)
        return container, button

    def _scroll_controllers(self, direction: int):
        scrollbar = self.controller_scroll.horizontalScrollBar()
        scrollbar.setValue(scrollbar.value() + direction * ControllerSlot.WIDTH)

    def _update_controller_navigation(self, *_):
        scrollbar = self.controller_scroll.horizontalScrollBar()
        has_overflow = scrollbar.maximum() > 0
        self.previous_controllers[1].setVisible(has_overflow and scrollbar.value() > 0)
        self.next_controllers[1].setVisible(has_overflow and scrollbar.value() < scrollbar.maximum())

    def refresh_battery(self):
        for slot in self.slots:
            if slot.device_key:
                slot.update_battery(self.manager.power_levels.get(slot.device_key, "unknown"))

    def profile_selected(self, key: str, profile: str):
        if profile and profile != self.settings.default_profile:
            self.settings.assignments[key] = profile
        else:
            self.settings.assignments.pop(key, None)
        save(self.settings)

    def set_primary(self, key: str):
        if key in self.manager.controllers:
            self.settings.primary_device = key
            save(self.settings)
            self._primary_snapshot = key
            self.refresh()

    def forget_device(self, key: str):
        if key in self.manager.controllers or key not in self.settings.known_devices:
            return
        name = self.settings.known_devices[key]
        answer = QMessageBox.question(
            self, tr("Forget this controller"),
            tr("Forget “{name}” and remove its profile assignment?").format(name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.settings.device_preferences.pop(key, None)
        self.settings.controller_mappings.pop(key, None)
        self.settings.known_devices.pop(key)
        self.settings.assignments.pop(key, None)
        if self.settings.primary_device == key:
            self.settings.primary_device = next(iter(self.manager.controllers), None)
        save(self.settings)
        self._known_snapshot = dict(self.settings.known_devices)
        self._primary_snapshot = self.settings.primary_device
        self.refresh()

    def manage_profiles(self):
        self.open_settings("profiles")

    def open_settings(self, initial_tab: str | None = None):
        dialog = SettingsDialog(
            self.settings, self, self.debug_window, initial_tab=initial_tab,
            controller_manager=self.manager)
        result = dialog.exec()
        self.manager.catalog = dialog.catalog
        if result != QDialog.DialogCode.Accepted:
            self.refresh()
            return
        self.settings.assignments = dialog.settings.assignments
        self.settings.device_preferences = dialog.settings.device_preferences
        self.settings.controller_mappings = dialog.settings.controller_mappings
        self.settings.display_controller_model = dialog.settings.display_controller_model
        self.settings.profiles = dialog.profiles
        self.settings.default_profile = dialog.default_profile_picker.currentText()
        self.settings.startup_enabled = dialog.startup_checkbox.isChecked()
        self.settings.start_minimized = dialog.minimized_checkbox.isChecked()
        self.settings.debug_window_on_startup = dialog.debug_startup_checkbox.isChecked()
        self.settings.game_mode_auto = dialog.game_auto_checkbox.isChecked()
        self.settings.games = executable_list(dialog.games_edit.text())
        self.settings.non_games = executable_list(dialog.non_games_edit.text())
        display_changed = dialog.display_changed()
        self.settings.language = dialog.language_picker.currentData()
        self.settings.theme = dialog.theme_picker.currentData()
        self.settings.controller_style = dialog.controller_style_picker.currentData()
        save(self.settings)
        self.refresh()
        try:
            configure_startup(self.settings)
        except OSError as exc:
            QMessageBox.warning(self, tr("{app} — Startup").format(app=APP_NAME), str(exc))
        if display_changed:
            answer = QMessageBox.question(
                self, tr("Restart {app}").format(app=APP_NAME),
                tr("Restart {app} now to apply the new language and theme?").format(app=APP_NAME),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes)
            if answer == QMessageBox.StandardButton.Yes:
                self.restart()

    def restart(self):
        """Start a new instance, which waits for this one to exit, then quit."""
        frozen = getattr(sys, "frozen", False)
        arguments = [argument for argument in sys.argv[0 if not frozen else 1:]
                     if argument != "--minimized"]
        arguments += [RESTART_FLAG, str(os.getpid())]
        if QProcess.startDetached(sys.executable, arguments)[0]:
            QApplication.quit()

    def show_debug_window(self):
        self.debug_window.showNormal()
        self.debug_window.raise_()
        self.debug_window.activateWindow()

    def show_for_device(self, device):
        self.refresh()
        self.show_from_tray()

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_from_tray()

    def show_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if self.tray.isVisible():
            event.ignore()
            self.hide()
        else:
            event.accept()
