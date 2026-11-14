"""Colour themes: derived colours, settings, Display tab and restart."""
import re
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QSize

from pawz.core.models import Settings
from pawz.ui import themes, windows


@pytest.fixture
def turquoise():
    themes.set_current(themes.COMFY_TURQUOISE)
    yield themes.current()
    themes.set_current(themes.MIDNIGHT_BLUE)


def source_colors() -> set[str]:
    return {color.lower() for color in re.findall(r"#[0-9a-fA-F]{6}\b", windows.CSS)}


def test_midnight_blue_is_the_source_palette_unchanged():
    assert themes.themed(windows.CSS, themes.THEMES[themes.MIDNIGHT_BLUE]) == windows.CSS


def test_comfy_turquoise_fills_buttons_with_the_accent_and_keeps_luminance_ratios():
    theme = themes.THEMES[themes.COMFY_TURQUOISE]
    assert themes.map_color(themes.BUTTON_FILL, theme.id) == "#00a8b0"
    assert theme.luminance_factor == pytest.approx(4.0, abs=0.05)
    for color in source_colors() - {themes.BRAND, themes.BUTTON_FILL}:
        mapped = themes.map_color(color, theme.id)
        if themes._is_blue(color):
            expected = min(1.0, themes.luminance(color) * theme.luminance_factor)
            assert themes.luminance(mapped) == pytest.approx(expected, abs=0.004), color
        else:
            assert mapped == color


def test_comfy_turquoise_turns_blues_turquoise_and_leaves_neutrals():
    assert themes.map_color("#ffffff", themes.COMFY_TURQUOISE) == "#ffffff"
    assert themes.map_color("#f26945", themes.COMFY_TURQUOISE) == "#f26945"  # low battery
    background = themes.map_color("#10233f", themes.COMFY_TURQUOISE)
    red, green, blue = (int(background[i:i + 2], 16) for i in (1, 3, 5))
    assert green > red and blue > red  # blue-green, no longer navy
    assert abs(green - blue) < 20


def test_turquoise_stylesheet_uses_the_accent_for_title_and_button_fill(turquoise):
    css = windows.stylesheet()
    assert "QLabel#settingsBrand { color:#00a8b0;" in css
    outline = themes.map_color(themes.BUTTON_OUTLINE, themes.COMFY_TURQUOISE)
    assert f"QPushButton {{ background:#00a8b0; border:1px solid {outline};" in css
    assert "#3187c7" not in css and "#223d68" not in css


def test_icons_and_inline_styles_follow_the_theme(qtbot, turquoise):
    button = windows.profile_action_button("Edit", "edit")
    qtbot.addWidget(button)
    assert "background:#00a8b0" in button.styleSheet() and "#20527b" not in button.styleSheet()
    icon = windows.action_icon("settings")
    assert not icon.isNull()
    assert not icon.pixmap(QSize(18, 18)).isNull()


def test_theme_setting_defaults_to_comfy_turquoise_and_round_trips():
    settings = Settings.defaults()
    assert settings.theme == themes.DEFAULT == themes.COMFY_TURQUOISE
    settings.theme = themes.MIDNIGHT_BLUE
    assert Settings.parse(settings.dump()).theme == themes.MIDNIGHT_BLUE
    raw = settings.dump()
    raw.pop("theme")
    assert Settings.parse(raw).theme == themes.COMFY_TURQUOISE  # existing settings files
    assert themes.set_current("unknown").id == themes.DEFAULT
    themes.set_current(themes.MIDNIGHT_BLUE)


def test_display_tab_lists_themes_and_flags_a_change(qtbot):
    dialog = windows.SettingsDialog(Settings.defaults())
    qtbot.addWidget(dialog)
    picker = dialog.theme_picker
    assert [picker.itemText(i) for i in range(picker.count())] == [
        "Comfy Turquoise", "Danger Red", "Midnight Blue"]
    assert picker.currentData() == themes.COMFY_TURQUOISE
    picker.setCurrentIndex(picker.findData(themes.MIDNIGHT_BLUE))
    assert dialog.display_changed() and not dialog.display_note.isHidden()


def test_restart_starts_a_new_instance_that_waits_for_this_one(monkeypatch):
    started = Mock(return_value=(True, 1234))
    quit_app = Mock()
    monkeypatch.setattr(windows.QProcess, "startDetached", started)
    monkeypatch.setattr(windows.QApplication, "quit", quit_app)
    monkeypatch.setattr(windows.sys, "argv", ["pawz.exe", "--minimized"])
    monkeypatch.setattr(windows.sys, "frozen", True, raising=False)
    monkeypatch.setattr(windows.os, "getpid", lambda: 42)
    windows.MainWindow.restart(Mock())
    started.assert_called_once_with(windows.sys.executable, [windows.RESTART_FLAG, "42"])
    quit_app.assert_called_once()


def test_new_instance_waits_for_the_previous_one_and_drops_the_flag(monkeypatch):
    import psutil

    from pawz import main
    waited = []
    monkeypatch.setattr(psutil, "Process",
                        lambda pid: Mock(wait=lambda timeout: waited.append((pid, timeout))))
    argv = ["pawz.exe", windows.RESTART_FLAG, "42", "--other"]
    main.wait_for_previous_instance(argv)
    assert argv == ["pawz.exe", "--other"]
    assert waited == [(42, 15)]


def test_danger_red_fills_buttons_red_with_one_hue_and_the_same_ratios():
    theme = themes.THEMES[themes.DANGER_RED]
    assert themes.map_color(themes.BUTTON_FILL, theme.id) == "#c62828"
    assert themes.map_color(themes.BRAND, theme.id) == "#c62828"
    accent_hue = themes._oklch("#c62828")[2]
    for color in source_colors() - {themes.BRAND, themes.BUTTON_FILL}:
        if not themes._is_blue(color):
            continue
        mapped = themes.map_color(color, theme.id)
        expected = min(1.0, themes.luminance(color) * theme.luminance_factor)
        assert themes.luminance(mapped) == pytest.approx(expected, abs=0.004), color
        lightness, chroma, hue = themes._oklch(mapped)
        if chroma > 0.03 and 0.1 < lightness < 0.95:  # hue is meaningless for greys
            assert abs((hue - accent_hue + 180) % 360 - 180) < 6, color
