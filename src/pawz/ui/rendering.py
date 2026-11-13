"""Native-DPI icon painting and smooth, scalable text metrics."""
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont, QIcon, QPainter
from PySide6.QtWidgets import QApplication, QLabel

ICON_DIR = Path(__file__).resolve().parent / "assets" / "icons"


@lru_cache(maxsize=16)
def vector_icon(name: str) -> QIcon:
    path = ICON_DIR / (name + ".svg")
    if not path.is_file():
        raise ValueError(f"Missing vector icon: {name}")
    icon = QIcon(str(path))
    disabled = path.with_name(name + "-disabled.svg")
    if disabled.is_file():
        icon.addFile(str(disabled), mode=QIcon.Mode.Disabled)
    return icon


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
