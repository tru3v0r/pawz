"""How controller illustrations are drawn: recoloured to fit the theme, or as shipped.

Styles work on the bundled SVGs (asset-pack silhouettes and pawz drawings), whose
dark areas are the controller's body and light areas its buttons and sticks:

- Eye Candy: dark areas take the body colour of Dark, light areas the button fill,
  and every element gets an outline in the button outline colour.
- Dark: each colour becomes a mix of a dark body colour and a light detail colour,
  following its lightness.
- Light: the same with a light body and the button fill for details.
- Original: the files' own colours.

Colours are written in Midnight Blue and mapped by the current theme, so every
style follows the theme. Unlike the theme, the style applies immediately.
"""
from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET

from pawz.i18n import QT_TR_NOOP
from pawz.ui import themes

EYE_CANDY, DARK, LIGHT, ORIGINAL = "eye_candy", "dark", "light", "original"
DEFAULT = EYE_CANDY
STYLES = {EYE_CANDY: QT_TR_NOOP("Eye Candy"), DARK: QT_TR_NOOP("Dark"),
          LIGHT: QT_TR_NOOP("Light"), ORIGINAL: QT_TR_NOOP("Original")}
# (body, details) in Midnight Blue colours.
PALETTES = {DARK: ("#10233f", "#65baff"), LIGHT: ("#f5f7fb", themes.BUTTON_FILL),
            EYE_CANDY: ("#10233f", themes.BUTTON_FILL)}
OUTLINE_WIDTH = 0.012  # Eye Candy outline, as a share of the drawing's largest side
# Eye Candy: shapes smaller than this share of the drawing are glyphs and symbols
# (letters on buttons, arrows): they stay light and get no outline, or they would
# vanish into their button.
GLYPH_SIZE = 0.035
SHAPES = {"path", "circle", "ellipse", "rect", "polygon", "polyline", "line"}
SVG_NS = "http://www.w3.org/2000/svg"
_HEX = re.compile(r"#[0-9a-fA-F]{6}\b")
_current = DEFAULT

ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")


def set_current(style: str) -> str:
    global _current
    _current = style if style in STYLES else DEFAULT
    return _current


def current() -> str:
    return _current


def _theme_color(color: str, theme: themes.Theme) -> str:
    return themes.map_color(color, theme.id) if theme.accent else color


def _lightness(color: str) -> float:
    return themes._oklch(color.lower())[0]


def _mix(body: str, detail: str, amount: float) -> str:
    b, d = themes._rgb(body), themes._rgb(detail)
    return "#" + "".join(f"{round((b[i] + (d[i] - b[i]) * amount) * 255):02x}" for i in range(3))


def _normalize(svg: str) -> str:
    return re.sub(r"(fill|stroke)(:|=\")(white|black)\b",
                  lambda m: f"{m.group(1)}{m.group(2)}{'#ffffff' if m.group(3) == 'white' else '#000000'}",
                  svg)


def styled(svg: str, style: str | None = None, theme: themes.Theme | None = None) -> str:
    """``svg`` drawn in ``style`` (default: the current one) and ``theme``'s colours."""
    style = style or _current
    theme = theme or themes.current()
    if style == ORIGINAL:
        return svg
    body, detail = (_theme_color(color, theme) for color in PALETTES[style])
    svg = _normalize(svg)
    if style in (DARK, LIGHT):
        return _HEX.sub(lambda m: _mix(body, detail, _lightness(m.group(0))), svg)
    return _eye_candy(svg, body, detail, _theme_color(themes.BUTTON_OUTLINE, theme))


# -- Eye Candy ------------------------------------------------------------------------

def _style_map(element) -> dict[str, str]:
    declarations = (part.split(":", 1) for part in (element.get("style") or "").split(";") if ":" in part)
    return {key.strip(): value.strip() for key, value in declarations}


def _scale(transform: str | None) -> float:
    """How much a ``transform`` attribute enlarges lengths (geometric mean of the axes)."""
    factor = 1.0
    for name, arguments in re.findall(r"(\w+)\s*\(([^)]*)\)", transform or ""):
        values = [float(v) for v in re.split(r"[\s,]+", arguments.strip()) if v]
        if name == "matrix" and len(values) == 6:
            factor *= math.sqrt(abs(values[0] * values[3] - values[1] * values[2]))
        elif name == "scale" and values:
            factor *= math.sqrt(abs(values[0] * (values[1] if len(values) > 1 else values[0])))
    return factor or 1.0


def _size(root) -> float:
    view_box = root.get("viewBox")
    if view_box:
        values = [float(v) for v in re.split(r"[\s,]+", view_box.strip())]
        return max(values[2], values[3])
    return max(float(re.match(r"[\d.]+", root.get(key) or "100").group(0)) for key in ("width", "height"))


def _small_elements(svg: str, limit: float) -> set[str]:
    """Ids of shapes drawn smaller than ``limit`` (drawing units) on both sides."""
    from PySide6.QtCore import QByteArray
    from PySide6.QtSvg import QSvgRenderer
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        return set()
    small = set()
    for element_id in re.findall(r'<(?:path|circle|ellipse|rect|polygon)\b[^<>]*?\bid="([^"]+)"', svg):
        if renderer.elementExists(element_id):
            bounds = renderer.transformForElement(element_id).mapRect(renderer.boundsOnElement(element_id))
            if 0 < max(bounds.width(), bounds.height()) < limit:
                small.add(element_id)
    return small


def _eye_candy(svg: str, body: str, buttons: str, outline: str) -> str:
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return svg
    size = _size(root)
    width = size * OUTLINE_WIDTH
    glyphs = _small_elements(svg, size * GLYPH_SIZE)

    def visit(element, scale: float, hidden: bool):
        style = _style_map(element)
        scale *= _scale(element.get("transform"))
        hidden = hidden or style.get("display") == "none" or element.get("display") == "none"
        if element.tag.split("}")[-1] in SHAPES and not hidden:
            fill = style.get("fill", element.get("fill", "#000000"))
            glyph = element.get("id") in glyphs
            if _HEX.fullmatch(fill or ""):
                light = _lightness(fill) >= 0.5
                fill = (outline if light else body) if glyph else (buttons if light else body)
            translucent = any(float(value) < 1 for value in (
                style.get("opacity", element.get("opacity", "1")),
                style.get("fill-opacity", element.get("fill-opacity", "1"))))
            if glyph:
                style["stroke"] = "none"
            elif not translucent:  # shadows and overlays keep no outline
                style.update({"stroke": outline, "stroke-width": f"{width / scale:g}",
                              "stroke-linejoin": "round", "stroke-opacity": "1"})
            style["fill"] = fill
            for attribute in ("fill", "stroke", "stroke-width"):
                element.attrib.pop(attribute, None)
            element.set("style", ";".join(f"{key}:{value}" for key, value in style.items()))
        for child in element:
            visit(child, scale, hidden)

    visit(root, 1.0, False)
    return ET.tostring(root, encoding="unicode")
