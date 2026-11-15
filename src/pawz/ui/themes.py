"""Colour themes.

The stylesheet, inline styles and icons are written in Corporate Blue colours.
Another theme maps each of those colours to its own. Comfy Turquoise makes the
button fill its accent #00a8b0 and keeps the luminance ratios between colours:
every blue's luminance is multiplied by the same factor (accent / button fill,
about 4, capped at white) and its hue turned towards the accent's. The app name
also takes the accent. Squishy Purple does the same with a dark purple fill, every
colour taking exactly the accent's hue, and bright purple button outlines and title.
Danger Red, Juicy Orange and Cheeky Green are bright: a vivid window colour, also
the buttons', and a darker one for panels, every other colour taking the window
colour's hue and vividness, with the luminance ratios kept. Light colours are tints
of the theme, never white: luminances past a knee are compressed. Neutral and status colours (battery, controller artwork,
YouTube red) are not blue and stay as they are.

The theme is chosen in Settings and applies at once. Everything themed follows a
change: the application stylesheet is set again, widgets styled with
``set_themed_style()`` are restyled, icons theme their SVG when painted, and widgets
that load themed drawings reload them on ``signals.changed``.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from functools import cache, lru_cache

from PySide6.QtCore import QByteArray, QObject, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QIcon, QIconEngine, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QWidget

from pawz import data_files

# The interface is written in Corporate Blue colours; themes (data/themes/themes.json)
# name them by role.
CORPORATE_BLUE = "midnight_blue"  # its id from an earlier name: saved settings use it
BRAND = "#3989cf"  # application name in window headers
BUTTON_FILL = "#20527b"  # button background
BUTTON_OUTLINE = "#3187c7"  # button borders
WINDOW_BACKGROUND = "#223d68"  # main window and dialogs
BUTTON_HOVER = "#28618e"  # hovered buttons and list items
SELECTION = "#2765cc"  # selected list item
PANEL = "#1b355b"  # the darker colour of panels, fields and lists
ROLES = {"brand": BRAND, "button_fill": BUTTON_FILL, "button_outline": BUTTON_OUTLINE,
         "window_background": WINDOW_BACKGROUND, "button_hover": BUTTON_HOVER,
         "selection": SELECTION, "panel": PANEL}
_DATA = data_files.load("themes/themes.json")
DEFAULT: str = _DATA["default"]
# Other themes draw hover and selection as darker shades of their button fill (the
# luminance ratio would make them lighter, up to white in bright themes).
SHADES = {ROLES[role]: share for role, share in _DATA["hover_shades"].items()}
_HEX = re.compile(r"#[0-9a-fA-F]{6}\b")


@dataclass(frozen=True)
class Theme:
    id: str
    name: str  # English label from the data file; display with tr()
    accent: str | None = None  # None: the source colours unchanged
    anchor: str = BUTTON_FILL  # the source colour that becomes the accent
    overrides: dict[str, str] = field(default_factory=dict)
    # True: blues keep their small hue differences around the accent; False: they all
    # take the accent's hue (near red, those differences drift into brown and orange).
    keep_hue_offsets: bool = True
    # True: every colour's chroma is scaled like the anchor's to the accent's, so a
    # vivid accent makes the whole theme as vivid (the blues are rather muted).
    match_chroma: bool = False

    @property
    def luminance_factor(self) -> float:
        """Every blue's luminance is multiplied by this, keeping the ratios between them."""
        return luminance(self.accent) / luminance(self.anchor) if self.accent else 1.0


THEMES = {entry["id"]: Theme(
    entry["id"], entry["label"], entry.get("accent"), ROLES[entry.get("anchor", "button_fill")],
    {ROLES[role]: colour for role, colour in entry.get("overrides", {}).items()},
    entry.get("keep_hue_offsets", True), entry.get("match_chroma", False))
    for entry in _DATA["themes"]}
_current = THEMES[CORPORATE_BLUE]


class _Signals(QObject):
    changed = Signal()  # after apply(): widgets holding themed drawings reload them


signals = _Signals()
_STYLE_PROPERTY = "pawzThemedStyle"  # a widget's style sheet in source colours


def set_current(theme_id: str) -> Theme:
    """Select the theme used by ``themed()``, ``stylesheet()`` and icons."""
    global _current
    _current = THEMES.get(theme_id, THEMES[DEFAULT])
    return _current


def set_themed_style(widget: QWidget, css: str, *, append: bool = False) -> None:
    """Give ``widget`` a style sheet written in source colours, in the current theme,
    and keep the source so a theme change restyles it."""
    if append:
        css = (widget.property(_STYLE_PROPERTY) or "") + css
    widget.setProperty(_STYLE_PROPERTY, css)
    widget.setStyleSheet(themed(css))


def apply(theme_id: str, application_css: str) -> Theme:
    """Switch the running application to ``theme_id``: its stylesheet (written in
    source colours), every widget styled with ``set_themed_style()``, icons and
    drawings."""
    theme = set_current(theme_id)
    app = QApplication.instance()
    if isinstance(app, QApplication):
        app.setStyleSheet(themed(application_css))
        for widget in app.allWidgets():
            css = widget.property(_STYLE_PROPERTY)
            if css is not None:
                widget.setStyleSheet(themed(css))
    signals.changed.emit()
    if isinstance(app, QApplication):
        for widget in app.allWidgets():
            widget.update()
    return theme


def current() -> Theme:
    return _current


def themed(text: str, theme: Theme | None = None) -> str:
    """``text`` (CSS or SVG) with its Corporate Blue colours in ``theme``'s colours."""
    theme = theme or _current
    if theme.accent is None:
        return text
    return _HEX.sub(lambda match: map_color(match.group(0), theme.id), text)


# -- colour mapping -------------------------------------------------------------------

def _to_linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def _to_srgb(channel: float) -> float:
    return 12.92 * channel if channel <= 0.0031308 else 1.055 * channel ** (1 / 2.4) - 0.055


def _rgb(color: str) -> tuple[float, float, float]:
    return tuple(int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))


def luminance(color: str) -> float:
    """WCAG relative luminance."""
    r, g, b = (_to_linear(c) for c in _rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _oklch(color: str) -> tuple[float, float, float]:
    r, g, b = (_to_linear(c) for c in _rgb(color))
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    lightness = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b2 = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return lightness, math.hypot(a, b2), math.degrees(math.atan2(b2, a)) % 360


def _linear_rgb(lightness: float, chroma: float, hue: float) -> tuple[float, float, float]:
    a, b = chroma * math.cos(math.radians(hue)), chroma * math.sin(math.radians(hue))
    l_ = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
            -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
            -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)


def _in_gamut(rgb) -> bool:
    return all(-1e-6 <= channel <= 1 + 1e-6 for channel in rgb)


def _hex(rgb) -> str:
    return "#" + "".join(f"{round(min(1, max(0, _to_srgb(c))) * 255):02x}" for c in rgb)


def _is_blue(color: str) -> bool:
    _, chroma, hue = _oklch(color)
    return chroma > 0.012 and 200 <= hue <= 290


@cache
def map_color(color: str, theme_id: str) -> str:
    theme = THEMES[theme_id]
    color = color.lower()
    if color in theme.overrides:
        return theme.overrides[color]
    if theme.accent is None or not _is_blue(color):
        return color
    if color in SHADES:
        _, chroma, hue = _oklch(map_color(BUTTON_FILL, theme_id))
        return _with_luminance(luminance(map_color(BUTTON_FILL, theme_id)) * SHADES[color], chroma, hue)
    target = scaled_luminance(luminance(color), theme)
    _, chroma, hue = _oklch(color)
    if theme.match_chroma:
        chroma *= _oklch(theme.accent)[1] / _oklch(theme.anchor)[1]
    hue = ((hue - _oklch(theme.anchor)[2] if theme.keep_hue_offsets else 0)
           + _oklch(theme.accent)[2]) % 360
    # Same hue shift for every blue, then the lightness that gives the scaled luminance.
    return _with_luminance(target, chroma, hue)


KNEE: float = _DATA["light_tints"]["knee"]  # scaled luminances above it are compressed
LIGHTEST: float = _DATA["light_tints"]["lightest"]  # below this


def scaled_luminance(value: float, theme: Theme) -> float:
    """``value`` times the theme's luminance factor; light results are compressed
    smoothly below ``LIGHTEST``, so they stay tints of the theme instead of turning
    white (the order of colours is kept)."""
    target = value * theme.luminance_factor
    if target <= KNEE:
        return target
    room = LIGHTEST - KNEE
    return KNEE + room * (1 - math.exp(-(target - KNEE) / room))


def _with_luminance(target: float, chroma: float, hue: float) -> str:
    """The colour of this OKLCH chroma and hue with relative luminance ``target``;
    chroma is reduced only when the colour would leave sRGB."""
    while True:
        low, high = 0.0, 1.0
        for _ in range(40):
            middle = (low + high) / 2
            r, g, b = _linear_rgb(middle, chroma, hue)
            if 0.2126 * r + 0.7152 * g + 0.0722 * b < target:
                low = middle
            else:
                high = middle
        rgb = _linear_rgb(high, chroma, hue)
        if _in_gamut(rgb) or chroma < 1e-3:
            return _hex(rgb)
        chroma *= 0.95


# -- icons ----------------------------------------------------------------------------

@lru_cache(maxsize=256)
def _themed_svg(source: str, theme_id: str) -> QByteArray:
    return QByteArray(themed(source, THEMES[theme_id]).encode("utf-8"))


class _SvgIconEngine(QIconEngine):
    """Paints SVG written in source colours, recoloured into the theme current when it
    paints, at any size (QIcon(path) would use the file's colours)."""

    def __init__(self, normal: str, disabled: str | None):
        super().__init__()
        self._data = {QIcon.Mode.Normal: normal, QIcon.Mode.Disabled: disabled or normal}

    def _renderer(self, mode) -> QSvgRenderer:
        source = self._data.get(mode, self._data[QIcon.Mode.Normal])
        return QSvgRenderer(_themed_svg(source, _current.id))

    def paint(self, painter: QPainter, rect: QRect, mode, state) -> None:
        renderer = self._renderer(mode)
        size = renderer.defaultSize().scaled(rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
        target = QRectF(rect.x() + (rect.width() - size.width()) / 2,
                        rect.y() + (rect.height() - size.height()) / 2, size.width(), size.height())
        renderer.render(painter, target)

    def pixmap(self, size: QSize, mode, state) -> QPixmap:
        pixmap = QPixmap(size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        self.paint(painter, QRect(0, 0, size.width(), size.height()), mode, state)
        painter.end()
        return pixmap

    def scaledPixmap(self, size: QSize, mode, state, scale: float) -> QPixmap:
        pixmap = self.pixmap(QSize(math.floor(size.width() * scale + 0.5),
                                   math.floor(size.height() * scale + 0.5)),
                             mode, state)
        pixmap.setDevicePixelRatio(scale)
        return pixmap

    def clone(self) -> QIconEngine:
        return _SvgIconEngine(self._data[QIcon.Mode.Normal], self._data[QIcon.Mode.Disabled])


@lru_cache(maxsize=32)
def themed_icon(normal_path: str, disabled_path: str | None = None) -> QIcon:
    """An SVG icon in the colours of the theme current when it is painted."""
    def load(path):
        with open(path, encoding="utf-8") as file:
            return file.read()
    return QIcon(_SvgIconEngine(load(normal_path), load(disabled_path) if disabled_path else None))
