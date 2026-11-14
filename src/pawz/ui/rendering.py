"""Native-DPI icon painting and smooth, scalable text metrics."""
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont, QIcon, QPainter
from PySide6.QtWidgets import QApplication, QLabel

from pawz.ui.themes import themed_icon

ICON_DIR = Path(__file__).resolve().parent / "assets" / "icons"


def vector_icon(name: str) -> QIcon:
    """An interface icon in the current theme's colours (cached per theme)."""
    path = ICON_DIR / (name + ".svg")
    if not path.is_file():
        raise ValueError(f"Missing vector icon: {name}")
    disabled = path.with_name(name + "-disabled.svg")
    return themed_icon(str(path), str(disabled) if disabled.is_file() else None)


def configure_text_rendering(app: QApplication) -> None:
    font = QFont(app.font())
    # DirectWrite's vertical hinting preserves natural horizontal metrics instead
    # of stretching each glyph to a different whole-pixel width at fractional DPI.
    font.setHintingPreference(QFont.HintingPreference.PreferVerticalHinting)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)


class ScalableIconLabel(QLabel):
    """Paint the original QIcon at the current screen's DPR, including screen moves."""

    def __init__(self, icon: QIcon, size: QSize, parent=None):
        super().__init__(parent)
        self.icon = icon
        self.setFixedSize(size)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        mode = QIcon.Mode.Normal if self.isEnabled() else QIcon.Mode.Disabled
        self.icon.paint(painter, self.rect(), Qt.AlignmentFlag.AlignCenter, mode)
