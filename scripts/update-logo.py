"""Regenerate the application logo from the working file in design/.

    python scripts/update-logo.py [design/logo/logo.svg]

Writes ``src/pawz/ui/assets/logo.svg`` (used by the interface) and ``logo.ico``
(16 to 256 px, the executable's icon). The SVG is framed square, centered, so
icons are not stretched, and PowerPoint's invisible text layer is removed.
"""
from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "design" / "logo" / "logo.svg"
ASSETS = ROOT / "src" / "pawz" / "ui" / "assets"
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def square_svg(svg: str) -> str:
    svg = re.sub(r"<text\b[^>]*\bfill-opacity=\"0\"[^>]*>.*?</text>", "", svg, flags=re.S)
    root = re.search(r"<svg\b[^>]*>", svg)
    if root is None:
        raise ValueError("not an SVG file")
    tag = root.group(0)
    width = float(re.search(r'\bwidth="([\d.]+)', tag).group(1))
    height = float(re.search(r'\bheight="([\d.]+)', tag).group(1))
    if "viewBox" in tag:
        raise ValueError("SVG with a viewBox: frame it square by hand")
    side = max(width, height)
    new_tag = re.sub(r'\bwidth="[\d.]+(px)?"', f'width="{side:g}"', tag, count=1)
    new_tag = re.sub(r'\bheight="[\d.]+(px)?"', f'height="{side:g}"', new_tag, count=1)
    new_tag = new_tag.replace(
        "<svg", f'<svg viewBox="{-(side - width) / 2:g} {-(side - height) / 2:g} {side:g} {side:g}"', 1)
    return svg.replace(tag, new_tag, 1)


def render(renderer: QSvgRenderer, size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return image


def ico(renderer: QSvgRenderer) -> bytes:
    images = []
    for size in ICO_SIZES:
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        render(renderer, size).save(buffer, "PNG")
        images.append((size, bytes(data)))
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries = b""
    for size, data in images:  # PNG-compressed entries; 256 is written as 0
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    return header + entries + b"".join(data for _, data in images)


def main() -> int:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else SOURCE
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])  # noqa: F841 - Qt needs it
    target = ASSETS / "logo.svg"
    target.write_text(square_svg(source.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    renderer = QSvgRenderer(str(target))
    if not renderer.isValid():
        raise SystemExit(f"Qt cannot render {source}")
    (ASSETS / "logo.ico").write_bytes(ico(renderer))
    print(f"Updated {target.name} and logo.ico from {source}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
