"""Name the inputs drawn in a controller illustration.

Clicking an element of the drawing and choosing a logical input gives that element
the input's name as its ``id`` (what the live display looks for) and as its Inkscape
layer name (``inkscape:label``). Only those attributes change in the file's text, so
a renamed asset-pack file differs from the original by the names alone.

Bundled drawings are never modified: the renamed copy goes to ``OVERRIDES_DIR``,
which pawz then uses instead, and for Gamepad Asset Pack files a second copy goes
to ``ASSET_PACK_EXPORT_DIR`` at the file's path in that repository, ready for a pull
request. Imported illustrations are renamed in place.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPen
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pawz.core.models import BUTTONS
from pawz.i18n import tr
from pawz.infra.storage import DATA_DIR
from pawz.ui.controller_assets import ASSET_DIR, OVERRIDES_DIR
from pawz.ui.themes import BUTTON_OUTLINE, themed

ASSET_PACK_EXPORT_DIR = DATA_DIR / "asset-pack-names"
ASSET_PACK_FOLDER = "Connection Icon Pack/Controller Type/SVG/"
# Bundled file -> its path in the Gamepad Asset Pack repository.
ASSET_PACK_FILES = {
    "library-generic.svg": "VSCView Generic Controller.svg",
    "library/xbox-360.svg": "VSCView Xbox 360 Controller.svg",
    "library/xbox-wireless.svg": "VSCView Xbox Wireless Controller.svg",
    "library/dualshock-3.svg": "VSCView DualShock 3 Controller.svg",
    "library/dualshock-4.svg": "VSCView DualShock 4 Controller.svg",
    "library/dualsense.svg": "VSCView DualSense Controller.svg",
    "library/switch-pro.svg": "VSCView Switch Pro Controller.svg",
    "library/joycon.svg": "VSCView Switch Joy-Con.svg",
    "library/joycon-grip.svg": "VSCView Switch Joy-Con Grip.svg",
    "library/steam-controller.svg": "VSCView Steam Controller.svg",
    "library/steam-deck.svg": "VSCView Steam Deck.svg",
}
INPUTS = (*BUTTONS, "LEFT_STICK", "RIGHT_STICK")
SELECTABLE = {"path", "circle", "ellipse", "rect", "polygon", "polyline", "g"}


@dataclass
class Element:
    id: str
    bounds: QRectF  # in the drawing's user units


def bundled_relative(path: Path) -> str | None:
    """``"library/switch-pro.svg"`` for a bundled drawing or its renamed copy."""
    for root in (ASSET_DIR, OVERRIDES_DIR):
        try:
            return path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
    return None


def rename_element(text: str, old: str, new: str) -> str:
    """Give element ``old`` the id and Inkscape label ``new``; everything else is kept."""
    tag = re.search(r'<[^<>!?]*?\bid="' + re.escape(old) + r'"[^<>]*>', text)
    if tag is None:
        raise KeyError(old)
    updated = tag.group(0).replace(f'id="{old}"', f'id="{new}"', 1)
    if "xmlns:inkscape" in text:
        if re.search(r'\binkscape:label="[^"]*"', updated):
            updated = re.sub(r'\binkscape:label="[^"]*"', f'inkscape:label="{new}"', updated, count=1)
        else:
            updated = updated.replace(f'id="{new}"', f'inkscape:label="{new}" id="{new}"', 1)
    text = text[:tag.start()] + updated + text[tag.end():]
    # Keep references to the element working.
    return text.replace(f'"#{old}"', f'"#{new}"').replace(f"url(#{old})", f"url(#{new})")


def logical_name(element_id: str) -> str | None:
    candidate = element_id.removeprefix("pawz-").upper()
    return candidate if candidate in INPUTS else None


def elements_of(text: str) -> list[Element]:
    """Visible, selectable elements with an id, and where they are drawn."""
    renderer = QSvgRenderer(QByteArray(text.encode("utf-8")))
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    found = []

    def visit(node, hidden: bool):
        tag = node.tag.split("}")[-1]
        style = node.get("style") or ""
        hidden = hidden or tag in ("defs", "clipPath", "mask", "pattern", "metadata") or (
            "display:none" in style.replace(" ", "")) or node.get("display") == "none"
        element_id = node.get("id")
        if not hidden and tag in SELECTABLE and element_id and renderer.elementExists(element_id):
            bounds = renderer.transformForElement(element_id).mapRect(renderer.boundsOnElement(element_id))
            if bounds.width() > 0 and bounds.height() > 0:
                found.append(Element(element_id, bounds))
        for child in node:
            visit(child, hidden)

    visit(root, False)
    return found


class DrawingPicker(QWidget):
    """The drawing in its own colours; click an element to select it."""
    picked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.renderer = QSvgRenderer(self)
        self.elements: list[Element] = []
        self.names: dict[str, str] = {}  # element id -> logical input
        self.selected: str | None = None
        self.hovered: str | None = None
        self.setMouseTracking(True)
        self.setMinimumSize(360, 260)

    def load(self, text: str, elements: list[Element]):
        self.renderer.load(QByteArray(text.encode("utf-8")))
        self.elements = elements
        self.update()

    def drawing_rect(self) -> QRectF:
        size = self.renderer.defaultSize()
        size.scale(self.width() - 20, self.height() - 20, Qt.AspectRatioMode.KeepAspectRatio)
        return QRectF((self.width() - size.width()) / 2, (self.height() - size.height()) / 2,
                      size.width(), size.height())

    def to_widget(self, bounds: QRectF) -> QRectF:
        rect, view = self.drawing_rect(), self.renderer.viewBoxF()
        sx, sy = rect.width() / view.width(), rect.height() / view.height()
        return QRectF(rect.x() + (bounds.x() - view.x()) * sx, rect.y() + (bounds.y() - view.y()) * sy,
                      bounds.width() * sx, bounds.height() * sy)

    def element_at(self, point: QPointF) -> str | None:
        """The smallest element under ``point``: a button rather than the body around it."""
        under = [element for element in self.elements if self.to_widget(element.bounds).contains(point)]
        if not under:
            return None
        return min(under, key=lambda element: element.bounds.width() * element.bounds.height()).id

    def mouseMoveEvent(self, event):
        hovered = self.element_at(event.position())
        if hovered != self.hovered:
            self.hovered = hovered
            self.update()

    def mousePressEvent(self, event):
        element = self.element_at(event.position())
        if element:
            self.selected = element
            self.picked.emit(element)
            self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.renderer.isValid():
            return
        self.renderer.render(painter, self.drawing_rect())
        accent = QColor(themed(BUTTON_OUTLINE))
        by_id = {element.id: element for element in self.elements}
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for element_id, logical in self.names.items():
            if element_id in by_id:
                area = self.to_widget(by_id[element_id].bounds)
                painter.setPen(QPen(accent, 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(area)
                # The name in a dark tag above the element, readable on any drawing.
                metrics = painter.fontMetrics()
                tag = QRectF(0, 0, metrics.horizontalAdvance(logical) + 8, metrics.height() + 2)
                tag.moveCenter(QPointF(area.center().x(), area.top() - tag.height() / 2 - 2))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(20, 20, 20, 200))
                painter.drawRoundedRect(tag, 4, 4)
                painter.setPen(QColor("#ffffff"))
                painter.drawText(tag, Qt.AlignmentFlag.AlignCenter, logical)
        for element_id, pen in ((self.hovered, QPen(QColor("#ffffff"), 1, Qt.PenStyle.DashLine)),
                                (self.selected, QPen(QColor("#ffd54a"), 2.5))):
            if element_id in by_id:
                painter.setPen(pen)
                painter.drawRect(self.to_widget(by_id[element_id].bounds).adjusted(-2, -2, 2, 2))


class InputNamesDialog(QDialog):
    """Assign logical inputs to the elements of an illustration, then save."""

    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Name inputs"))
        self.setObjectName("inputNamesDialog")
        self.resize(760, 460)
        self.source = path
        self.relative = bundled_relative(path)
        with open(path, encoding="utf-8", newline="") as file:  # keep the line endings
            self.text = file.read()
        self.elements = elements_of(self.text)
        # Current names: elements already called after an input.
        self.names = {element.id: logical_name(element.id) for element in self.elements
                      if logical_name(element.id)}
        root = QVBoxLayout(self)
        intro = QLabel(tr("Click a button, stick or trigger in the drawing, then choose the input it is. "
                          "The element gets that name as its id and Inkscape layer name."))
        intro.setWordWrap(True)
        root.addWidget(intro)
        body = QHBoxLayout()
        self.picker = DrawingPicker()
        self.picker.setObjectName("inputNamesDrawing")
        self.picker.load(self.text, self.elements)
        self.picker.names = self.names
        self.picker.picked.connect(self._select)
        body.addWidget(self.picker, 3)
        side = QVBoxLayout()
        form = QFormLayout()
        self.element_label = QLabel("—")
        self.element_label.setObjectName("selectedElement")
        form.addRow(tr("Element"), self.element_label)
        self.input_picker = QComboBox()
        self.input_picker.setObjectName("inputPicker")
        self.input_picker.addItem(tr("— none —"), None)
        for logical in INPUTS:
            self.input_picker.addItem(logical, logical)
        self.input_picker.setEnabled(False)
        self.input_picker.currentIndexChanged.connect(self._assign)
        form.addRow(tr("Input"), self.input_picker)
        side.addLayout(form)
        self.assigned = QListWidget()
        self.assigned.setObjectName("assignedInputs")
        self.assigned.currentItemChanged.connect(
            lambda item, _previous: item and self._select(item.data(Qt.ItemDataRole.UserRole)))
        side.addWidget(self.assigned, 1)
        body.addLayout(side, 2)
        root.addLayout(body, 1)
        self.destination_note = QLabel(self._destination_text())
        self.destination_note.setWordWrap(True)
        self.destination_note.setObjectName("destinationNote")
        root.addWidget(self.destination_note)
        buttons = QHBoxLayout()
        self.open_folder = QPushButton(tr("Open the asset-pack folder"))
        self.open_folder.setVisible(self.relative in ASSET_PACK_FILES)
        self.open_folder.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(ASSET_PACK_EXPORT_DIR))))
        buttons.addWidget(self.open_folder)
        buttons.addStretch(1)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.save)
        box.rejected.connect(self.reject)
        buttons.addWidget(box)
        root.addLayout(buttons)
        self._refresh_list()

    def _destination_text(self) -> str:
        if self.relative is None:
            return tr("Saved in this imported illustration.")
        text = tr("Bundled drawings stay untouched: pawz saves a renamed copy and uses it instead.")
        if self.relative in ASSET_PACK_FILES:
            text += " " + tr("A copy at its Gamepad Asset Pack path is also saved in {folder}, "
                             "ready for a pull request.").format(folder=ASSET_PACK_EXPORT_DIR)
        return text

    def _select(self, element_id: str | None):
        if not element_id:
            return
        self.picker.selected = element_id
        self.picker.update()
        self.element_label.setText(element_id)
        self.input_picker.blockSignals(True)
        self.input_picker.setEnabled(True)
        self.input_picker.setCurrentIndex(max(0, self.input_picker.findData(self.names.get(element_id))))
        self.input_picker.blockSignals(False)

    def _assign(self, *_):
        element_id = self.picker.selected
        if not element_id:
            return
        logical = self.input_picker.currentData()
        for other, name in list(self.names.items()):
            if name == logical or other == element_id:
                del self.names[other]  # one element per input, one input per element
        if logical:
            self.names[element_id] = logical
        self._refresh_list()
        self.picker.update()

    def _refresh_list(self):
        self.assigned.blockSignals(True)
        self.assigned.clear()
        for element_id, logical in sorted(self.names.items(), key=lambda item: INPUTS.index(item[1])):
            item = QListWidgetItem(f"{logical}  ←  {element_id}")
            item.setData(Qt.ItemDataRole.UserRole, element_id)
            self.assigned.addItem(item)
        self.assigned.blockSignals(False)

    def renamed_text(self) -> str:
        """The file with the chosen names; unassigned elements keep or lose theirs."""
        text = self.text
        for element in self.elements:
            wanted = self.names.get(element.id)
            if wanted and wanted != element.id:
                text = rename_element(text, element.id, wanted)
            elif not wanted and logical_name(element.id):
                text = rename_element(text, element.id, f"unnamed-{element.id.lower()}")
        return text

    def save(self):
        text = self.renamed_text()
        try:
            if self.relative is None:
                self.source.write_text(text, encoding="utf-8", newline="")
            else:
                override = OVERRIDES_DIR / self.relative
                override.parent.mkdir(parents=True, exist_ok=True)
                override.write_text(text, encoding="utf-8", newline="")
                if self.relative in ASSET_PACK_FILES:
                    export = ASSET_PACK_EXPORT_DIR / ASSET_PACK_FOLDER / ASSET_PACK_FILES[self.relative]
                    export.parent.mkdir(parents=True, exist_ok=True)
                    export.write_text(text, encoding="utf-8", newline="")
        except OSError as exc:
            QMessageBox.warning(self, tr("Name inputs"), str(exc))
            return
        self.accept()
