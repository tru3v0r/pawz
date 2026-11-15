"""Controller artwork styles: recolouring, outlines, setting and Display tab."""
import re
import xml.etree.ElementTree as ET

import pytest
from PySide6.QtSvg import QSvgRenderer

from pawz.core.models import Settings
from pawz.ui import artwork_styles as styles
from pawz.ui import themes
from pawz.ui.controller_assets import ASSET_DIR, artwork_bytes

SWITCH_PRO = ASSET_DIR / "library" / "switch-pro.svg"
TURQUOISE = themes.THEMES[themes.COMFY_TURQUOISE]


def colors(svg: str) -> set[str]:
    return {color.lower() for color in re.findall(r"#[0-9a-fA-F]{6}\b", svg)}


@pytest.mark.parametrize("style", list(styles.STYLES))
@pytest.mark.parametrize("theme", list(themes.THEMES))
def test_every_style_renders_every_bundled_drawing(qapp, style, theme):
    for path in [*(ASSET_DIR / "library").glob("*.svg"), *(ASSET_DIR / "models").glob("*.svg"),
                 ASSET_DIR / "library-generic.svg"]:
        svg = styles.styled(path.read_text(encoding="utf-8"), style, themes.THEMES[theme])
        assert QSvgRenderer(svg.encode()).isValid(), path.name


def test_original_keeps_the_file():
    text = SWITCH_PRO.read_text(encoding="utf-8")
    assert styles.styled(text, styles.ORIGINAL, TURQUOISE) == text


def test_dark_and_light_use_their_palette_in_the_theme():
    text = SWITCH_PRO.read_text(encoding="utf-8")
    dark = colors(styles.styled(text, styles.DARK, TURQUOISE))
    assert themes.map_color("#10233f", TURQUOISE.id) in dark and "#ffffff" in dark  # body, details
    light = colors(styles.styled(text, styles.LIGHT, TURQUOISE))
    assert "#f5f7fb" in light and "#00a8b0" in light
    assert "#000000" not in dark | light


def test_eye_candy_fills_by_lightness_and_outlines_every_visible_shape():
    svg = styles.styled(SWITCH_PRO.read_text(encoding="utf-8"), styles.EYE_CANDY, TURQUOISE)
    body, buttons = themes.map_color("#10233f", TURQUOISE.id), "#00a8b0"
    outline = themes.map_color(themes.BUTTON_OUTLINE, TURQUOISE.id)
    shapes = [element for element in ET.fromstring(svg).iter()
              if element.tag.split("}")[-1] in styles.SHAPES]
    fills = {styles._style_map(shape)["fill"] for shape in shapes}
    assert fills == {body, buttons}
    for shape in shapes:
        assert styles._style_map(shape)["stroke"] == outline
    # The body path is scaled by its transform: its stroke compensates for it.
    widths = sorted(float(styles._style_map(shape)["stroke-width"]) for shape in shapes)
    assert widths[-1] == pytest.approx(widths[0] / 0.26458333, rel=0.01)


def test_eye_candy_skips_hidden_and_translucent_shapes():
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
           '<ellipse cx="50" cy="90" rx="40" ry="5" fill="#000000" opacity="0.3"/>'
           '<path d="M0 0h10v10z" style="display:none;fill:#00ff87"/>'
           '<circle cx="50" cy="50" r="20" fill="white"/></svg>')
    root = ET.fromstring(styles.styled(svg, styles.EYE_CANDY, themes.THEMES[themes.CORPORATE_BLUE]))
    shadow, hidden, button = list(root)
    assert "stroke" not in styles._style_map(shadow)
    assert styles._style_map(hidden).get("fill") == "#00ff87"
    assert styles._style_map(button) == {"fill": "#20527b", "stroke": "#3187c7", "stroke-width": "1.2",
                                         "stroke-linejoin": "round", "stroke-opacity": "1"}


def test_only_bundled_controller_artwork_is_styled(tmp_path):
    styles.set_current(styles.EYE_CANDY)
    own = tmp_path / "mine.svg"
    own.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
                   '<circle cx="5" cy="5" r="4" fill="#000000"/></svg>')
    assert artwork_bytes(own) == own.read_bytes()
    assert artwork_bytes(SWITCH_PRO) != SWITCH_PRO.read_bytes()
    prompt = next((ASSET_DIR / "prompts").rglob("*.svg"))
    assert artwork_bytes(prompt) == prompt.read_bytes()


def test_style_setting_defaults_to_eye_candy_and_round_trips():
    settings = Settings.defaults()
    assert settings.controller_style == styles.DEFAULT == styles.EYE_CANDY
    settings.controller_style = styles.LIGHT
    assert Settings.parse(settings.dump()).controller_style == styles.LIGHT
    raw = settings.dump()
    raw.pop("controller_style")
    assert Settings.parse(raw).controller_style == styles.EYE_CANDY
    assert styles.set_current("unknown") == styles.EYE_CANDY


def test_display_tab_previews_the_style_and_restores_it_on_cancel(qtbot):
    from pawz.ui.windows import SettingsDialog
    styles.set_current(styles.EYE_CANDY)
    dialog = SettingsDialog(Settings.defaults())
    qtbot.addWidget(dialog)
    picker = dialog.controller_style_picker
    assert [picker.itemText(i) for i in range(picker.count())] == ["Eye Candy", "Dark", "Light", "Original"]
    assert picker.currentData() == styles.EYE_CANDY
    picker.setCurrentIndex(picker.findData(styles.LIGHT))
    assert styles.current() == styles.LIGHT
    assert not dialog.display_note.isVisible() and not dialog.display_changed()  # no restart needed
    dialog.reject()
    assert styles.current() == styles.EYE_CANDY


def test_eye_candy_keeps_small_glyphs_light_and_unoutlined():
    path = ASSET_DIR / "library" / "switch-pro-detailed.svg"
    svg = styles.styled(path.read_text(encoding="utf-8"), styles.EYE_CANDY, TURQUOISE)
    root = ET.fromstring(svg)
    letter = next(node for node in root.iter() if node.get("id") == "path5694")  # the X on its button
    style = styles._style_map(letter)
    assert style["stroke"] == "none"
    assert style["fill"] == themes.map_color(themes.BUTTON_OUTLINE, TURQUOISE.id)
