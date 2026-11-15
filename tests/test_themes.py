"""Colour themes: derived colours, settings, Display tab and restart."""
import re
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QSize

from pawz.core.models import Settings
from pawz.ui import themes, windows


@pytest.fixture
def turquoise():
    themes.set_current(themes.COMFY_TURQUOISE)
    yield themes.current()
    themes.set_current(themes.CORPORATE_BLUE)


def source_colors() -> set[str]:
    return {color.lower() for color in re.findall(r"#[0-9a-fA-F]{6}\b", windows.CSS)}


def test_corporate_blue_is_the_source_palette_unchanged():
    assert themes.themed(windows.CSS, themes.THEMES[themes.CORPORATE_BLUE]) == windows.CSS


def test_comfy_turquoise_fills_buttons_with_the_accent_and_keeps_luminance_ratios():
    theme = themes.THEMES[themes.COMFY_TURQUOISE]
    assert themes.map_color(themes.BUTTON_FILL, theme.id) == "#00a8b0"
    assert theme.luminance_factor == pytest.approx(4.0, abs=0.05)
    for color in source_colors() - {themes.BRAND, themes.BUTTON_FILL} - set(themes.SHADES):
        mapped = themes.map_color(color, theme.id)
        if themes._is_blue(color):
            expected = themes.scaled_luminance(themes.luminance(color), theme)
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
    settings.theme = themes.CORPORATE_BLUE
    assert Settings.parse(settings.dump()).theme == themes.CORPORATE_BLUE
    raw = settings.dump()
    raw.pop("theme")
    assert Settings.parse(raw).theme == themes.COMFY_TURQUOISE  # existing settings files
    assert themes.set_current("unknown").id == themes.DEFAULT
    themes.set_current(themes.CORPORATE_BLUE)


def test_display_tab_lists_themes_and_previews_them_at_once(qtbot, qapp):
    qapp.setStyleSheet(windows.stylesheet())
    dialog = windows.SettingsDialog(Settings.defaults())
    qtbot.addWidget(dialog)
    picker = dialog.theme_picker
    assert [picker.itemText(i) for i in range(picker.count())] == [
        "Cheeky Green", "Comfy Turquoise", "Corporate Blue", "Danger Red", "Juicy Orange",
        "Squishy Purple"]
    assert picker.currentData() == themes.COMFY_TURQUOISE
    try:
        picker.setCurrentIndex(picker.findData(themes.DANGER_RED))
        assert themes.current().id == themes.DANGER_RED
        assert "#c0392b" in qapp.styleSheet() and "#c0392b" in dialog.styleSheet()
        assert not dialog.display_changed() and dialog.display_note.isHidden()  # no restart
        dialog.reject()  # Close without saving: back to the theme in use
        assert themes.current().id == themes.CORPORATE_BLUE
        assert qapp.styleSheet() == windows.CSS
    finally:
        qapp.setStyleSheet("")


def _scene(monkeypatch):
    monkeypatch.setattr(windows, "save", lambda _settings: None)
    settings = Settings.defaults()
    settings.primary_device = "pad#0"
    settings.known_devices = {"pad#0": "Nintendo Switch Pro Controller", "old#0": "Xbox Controller"}

    class Signal:
        def connect(self, _callback):
            pass

    manager = SimpleNamespace(
        controllers={"pad#0": SimpleNamespace(name="Nintendo Switch Pro Controller")},
        power_levels={"pad#0": "full"}, devices_changed=Signal(), controller_button_event=Signal(),
        live_state={})
    return settings, manager


def _screens(qapp, settings, manager, switch_to=None):
    """Main window and every Settings tab, built in the current theme, then switched
    live to ``switch_to`` when given."""
    window = windows.MainWindow(settings, manager)
    dialog = windows.SettingsDialog(settings)
    dialog.resize(708, 720)
    window.show()
    dialog.show()
    qapp.processEvents()
    for slot in window.findChildren(windows.ControllerSlot):  # battery fill at its end value
        animation = slot.battery_animation
        if animation.state() == windows.QPropertyAnimation.State.Running:
            animation.setCurrentTime(animation.duration())
    if switch_to:
        windows.apply_theme(switch_to)
    images = []
    for tab in range(dialog.tabs.count()):
        dialog.tabs.setCurrentIndex(tab)
        qapp.processEvents()
        images.append(dialog.grab().toImage())
    images.append(window.grab().toImage())
    window.tray.hide()
    dialog.close()
    window.close()
    return images


@pytest.mark.parametrize("theme_id", [themes.SQUISHY_PURPLE, themes.COMFY_TURQUOISE])
def test_a_live_theme_switch_looks_exactly_like_starting_in_that_theme(qapp, monkeypatch, theme_id):
    settings, manager = _scene(monkeypatch)
    try:
        qapp.setStyleSheet(windows.stylesheet())
        switched = _screens(qapp, settings, manager, switch_to=theme_id)
        themes.set_current(theme_id)
        qapp.setStyleSheet(windows.stylesheet())
        started = _screens(qapp, settings, manager)
    finally:
        themes.set_current(themes.CORPORATE_BLUE)
        qapp.setStyleSheet("")
    names = [f"settings tab {index}" for index in range(len(started) - 1)] + ["main window"]
    for name, live, fresh in zip(names, switched, started, strict=True):
        assert live == fresh, f"{name} keeps colours of the previous theme"


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


@pytest.mark.parametrize(("theme_id", "window", "dark"), [
    (themes.DANGER_RED, "#c0392b", "#9e0000"),
    (themes.JUICY_ORANGE, "#f39c12", "#fa8f00"),
    (themes.CHEEKY_GREEN, "#27ae60", "#1c7e46"),
])
def test_bright_themes_use_their_window_and_dark_colours_and_are_as_vivid(theme_id, window, dark):
    theme = themes.THEMES[theme_id]
    assert themes.map_color(themes.WINDOW_BACKGROUND, theme_id) == window
    assert themes.map_color(themes.PANEL, theme_id) == dark
    assert themes.map_color(themes.BUTTON_FILL, theme_id) == window  # buttons take the window colour
    _, window_chroma, window_hue = themes._oklch(window)
    for color in source_colors() - set(theme.overrides) - set(themes.SHADES):
        if not themes._is_blue(color):
            continue
        mapped = themes.map_color(color, theme_id)
        expected = themes.scaled_luminance(themes.luminance(color), theme)
        assert themes.luminance(mapped) == pytest.approx(expected, abs=0.004), color
        lightness, chroma, hue = themes._oklch(mapped)
        if chroma > 0.03 and 0.1 < lightness < 0.95:  # hue is meaningless for greys
            assert abs((hue - window_hue + 180) % 360 - 180) < 6, color
    # Not the muted look of the blues: colours are about as vivid as the window.
    darkest = themes._oklch(themes.map_color("#10233f", theme_id))[1]
    assert darkest > 0.6 * window_chroma


@pytest.mark.parametrize(("theme_id", "fill", "outline"), [
    (themes.SQUISHY_PURPLE, "#6d329a", "#b026ff"),
])
def test_dark_themes_have_bright_outlines_one_hue_and_the_same_ratios(theme_id, fill, outline):
    theme = themes.THEMES[theme_id]
    assert themes.map_color(themes.BUTTON_FILL, theme.id) == fill
    assert themes.map_color(themes.BRAND, theme.id) == outline
    assert themes.map_color(themes.BUTTON_OUTLINE, theme.id) == outline
    assert theme.luminance_factor == pytest.approx(1.0, abs=0.05)  # as dark as Corporate Blue
    accent_hue = themes._oklch(fill)[2]
    for color in source_colors() - {themes.BRAND, themes.BUTTON_FILL, themes.BUTTON_OUTLINE} - set(themes.SHADES):
        if not themes._is_blue(color):
            continue
        mapped = themes.map_color(color, theme.id)
        expected = themes.scaled_luminance(themes.luminance(color), theme)
        assert themes.luminance(mapped) == pytest.approx(expected, abs=0.004), color
        lightness, chroma, hue = themes._oklch(mapped)
        if chroma > 0.03 and 0.1 < lightness < 0.95:  # hue is meaningless for greys
            assert abs((hue - accent_hue + 180) % 360 - 180) < 6, color


@pytest.mark.parametrize("theme_id", sorted(set(themes.THEMES) - {themes.CORPORATE_BLUE}))
def test_hover_and_selection_are_darker_shades_of_the_button_fill(theme_id):
    fill = themes.map_color(themes.BUTTON_FILL, theme_id)
    hover = themes.map_color(themes.BUTTON_HOVER, theme_id)
    selection = themes.map_color(themes.SELECTION, theme_id)
    assert themes.luminance(selection) < themes.luminance(hover) < themes.luminance(fill)
    for shade in (hover, selection):
        assert abs((themes._oklch(shade)[2] - themes._oklch(fill)[2] + 180) % 360 - 180) < 6, shade


def test_theme_list_shows_a_sample_of_each_theme(qtbot):
    dialog = windows.SettingsDialog(Settings.defaults())
    qtbot.addWidget(dialog)
    assert isinstance(dialog.theme_picker.itemDelegate(), windows.ThemeSwatchDelegate)
    assert len(windows.ThemeSwatchDelegate.SAMPLED) == 5


@pytest.mark.parametrize("theme_id", sorted(set(themes.THEMES) - {themes.CORPORATE_BLUE}))
def test_light_colours_stay_tints_of_the_theme_instead_of_white(theme_id):
    for color in source_colors():
        if themes._is_blue(color):
            assert themes.luminance(themes.map_color(color, theme_id)) <= themes.LIGHTEST + 0.005, color
    lightest = [themes.scaled_luminance(value, themes.THEMES[theme_id]) for value in (0.3, 0.6, 0.9)]
    assert lightest == sorted(lightest)  # compression keeps the order of colours
