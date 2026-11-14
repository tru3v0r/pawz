"""Colour themes.

The stylesheet, inline styles and icons are written in Midnight Blue colours.
Another theme maps each of those colours to its own. Comfy Turquoise makes the
button fill its accent #00a8b0 and keeps the luminance ratios between colours:
every blue's luminance is multiplied by the same factor (accent / button fill,
about 4, capped at white) and its hue turned towards the accent's. The app name
also takes the accent. Danger Red does the same with a dark red fill, every colour
taking exactly the accent's hue, and bright red button outlines and title. Neutral and status colours (battery, controller artwork,
YouTube red) are not blue and stay as they are.

The theme is chosen in Settings and applied at startup, like the language.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from functools import cache, lru_cache

from PySide6.QtCore import QByteArray, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QIconEngine, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from pawz.i18n import QT_TR_NOOP

MIDNIGHT_BLUE = "midnight_blue"
COMFY_TURQUOISE = "comfy_turquoise"
DANGER_RED = "danger_red"
DEFAULT = COMFY_TURQUOISE
BRAND = "#3989cf"  # application name in window headers
BUTTON_FILL = "#20527b"  # button background
BUTTON_OUTLINE = "#3187c7"  # button borders
_HEX = re.compile(r"#[0-9a-fA-F]{6}\b")


@dataclass(frozen=True)
class Theme:
    id: str
    name: str  # marked for translation; display with tr()
    accent: str | None = None  # None: the source colours unchanged
    anchor: str = BUTTON_FILL  # the source colour that becomes the accent
    overrides: dict[str, str] = field(default_factory=dict)
    # True: blues keep their small hue differences around the accent; False: they all
    # take the accent's hue (near red, those differences drift into brown and orange).
    keep_hue_offsets: bool = True

    @property
    def luminance_factor(self) -> float:
        """Every blue's luminance is multiplied by this, keeping the ratios between them."""
        return luminance(self.accent) / luminance(self.anchor) if self.accent else 1.0


THEMES = {theme.id: theme for theme in (
    Theme(COMFY_TURQUOISE, QT_TR_NOOP("Comfy Turquoise"), "#00a8b0", BUTTON_FILL,
          {BRAND: "#00a8b0", BUTTON_FILL: "#00a8b0"}),
    # Dark like Midnight Blue (the fill has about its luminance), with bright red
    # button outlines and title.
    Theme(DANGER_RED, QT_TR_NOOP("Danger Red"), "#9b1c1c", BUTTON_FILL,
          {BRAND: "#ff2d2d", BUTTON_FILL: "#9b1c1c", BUTTON_OUTLINE: "#ff2d2d"},
          keep_hue_offsets=False),
    Theme(MIDNIGHT_BLUE, QT_TR_NOOP("Midnight Blue")),
)}
_current = THEMES[MIDNIGHT_BLUE]


def set_current(theme_id: str) -> Theme:
    """Select the theme used by ``themed()``, ``stylesheet()`` and icons."""
    global _current
    _current = THEMES.get(theme_id, THEMES[DEFAULT])
    themed_icon.cache_clear()
    return _current


def current() -> Theme:
    return _current


def themed(text: str, theme: Theme | None = None) -> str:
    """``text`` (CSS or SVG) with its Midnight Blue colours in ``theme``'s colours."""
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
    target = luminance(color) * theme.luminance_factor
    if target >= 1:
        return "#ffffff"
    _, chroma, hue = _oklch(color)
    hue = ((hue - _oklch(theme.anchor)[2] if theme.keep_hue_offsets else 0)
           + _oklch(theme.accent)[2]) % 360
    # Same hue shift for every blue, then the lightness that gives the scaled
    # luminance; chroma is reduced only when the colour would leave sRGB.
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

class _SvgIconEngine(QIconEngine):
    """Paints recoloured SVG data at any size (QIcon(path) would use the file's colours)."""

    def __init__(self, normal: bytes, disabled: bytes | None):
        super().__init__()
        self._data = {QIcon.Mode.Normal: normal, QIcon.Mode.Disabled: disabled or normal}

    def _renderer(self, mode) -> QSvgRenderer:
        return QSvgRenderer(QByteArray(self._data.get(mode, self._data[QIcon.Mode.Normal])))

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
    """An SVG icon in the current theme's colours."""
    def load(path):
        with open(path, encoding="utf-8") as file:
            return themed(file.read()).encode("utf-8")
    return QIcon(_SvgIconEngine(load(normal_path), load(disabled_path) if disabled_path else None))
