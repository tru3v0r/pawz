"""Cached Qt SVG resources, with explicit device/model/family fallback."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from functools import lru_cache
from html import escape
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

from pawz.core.controller_catalog import ControllerDefinition
from pawz.infra.storage import DATA_DIR
from pawz.ui.themes import themed

ASSET_DIR = Path(__file__).resolve().parent / "assets" / "controllers"


def prompt_path(logical: str, model: ControllerDefinition | None) -> Path | None:
    """Select reviewed upstream vectors by position, independently of bindings."""
    family = model.family if model else "generic"
    labels = model.physical_labels if model else {}
    if logical in ("LEFT_X", "LEFT_Y", "RIGHT_X", "RIGHT_Y"):
        return ASSET_DIR / "input-icons" / (logical.lower().replace("_", "-") + ".svg")
    shared = {
        "LEFT_SHOULDER": "Left Bumper", "RIGHT_SHOULDER": "Right Bumper",
        "LEFT_TRIGGER": "Left Trigger", "RIGHT_TRIGGER": "Right Trigger",
        "LEFT_STICK": "Left Stick Click", "RIGHT_STICK": "Right Stick Click",
        "BACK": "Select", "START": "Start", "DPAD_UP": "D-PAD Up",
        "DPAD_DOWN": "D-PA Down", "DPAD_LEFT": "D-PAD Left", "DPAD_RIGHT": "D-PAD Right",
    }
    relative = "Shared/shared-" + shared[logical] + ".svg" if logical in shared else None
    if logical in ("SOUTH", "EAST", "WEST", "NORTH"):
        label = labels.get(logical)
        if family == "playstation":
            label = {"SOUTH": "Cross", "EAST": "Circle", "WEST": "Square", "NORTH": "Triangle"}[logical]
            relative = f"PlayStation/ps-{label}.svg"
        elif label in ("A", "B", "X", "Y"):
            relative = f"Shared/shared-{label}.svg"
        else:
            position = {"SOUTH": "A", "EAST": "B", "WEST": "X", "NORTH": "Y"}[logical]
            relative = f"Shared/shared-{position}-Color.svg"
    if family == "nintendo":
        names = {"LEFT_SHOULDER": "L", "RIGHT_SHOULDER": "R", "LEFT_TRIGGER": "ZL",
                 "RIGHT_TRIGGER": "ZR", "LEFT_STICK": "L Click", "RIGHT_STICK": "R Click",
                 "BACK": "Minus", "START": "Plus"}
        if logical in names:
            relative = f"Nintendo/nintendo-{names[logical]}.svg"
    elif family == "playstation":
        names = {"LEFT_SHOULDER": "L1", "RIGHT_SHOULDER": "R1", "LEFT_TRIGGER": "L2",
                 "RIGHT_TRIGGER": "R2", "LEFT_STICK": "L3 Click", "RIGHT_STICK": "R3 Click"}
        if logical in names:
            relative = f"Shared/shared-{names[logical]}.svg"
        if logical == "BACK":
            relative = "PlayStation/ps3-Select.svg" if model.id == "sony.dualshock-3" else "PlayStation/ps4-Share.svg"
        elif logical == "START":
            relative = "PlayStation/ps3-Start.svg" if model.id == "sony.dualshock-3" else "PlayStation/ps4-Option.svg"
    elif family == "xbox" and logical in ("BACK", "START", "MISC1"):
        relative = "Xbox/xbox-" + {"BACK": "View", "START": "Menu", "MISC1": "Share"}[logical] + ".svg"
    if logical.startswith("PADDLE"):
        relative = "Xbox/xbox-P" + logical[-1] + ".svg"
    path = ASSET_DIR / "prompts" / relative if relative else None
    if path:
        colored = path.with_name(path.stem + "-Color.svg")
        if colored.is_file():
            path = colored
    return path if path and path.is_file() else None


@lru_cache(maxsize=256)
def prompt_svg(path: str) -> bytes:
    """Enable upstream's black outline variant for contrast on the dark panel."""
    root = ET.fromstring(Path(path).read_bytes())
    label_attr = "{http://www.inkscape.org/namespaces/inkscape}label"
    for parent in root.iter():
        variants = [child for child in parent if child.get(label_attr, "").startswith("Style -")]
        selected = next((child for child in variants if child.get(label_attr) == "Style - Outline (Black)"), None)
        if selected is not None:
            for child in variants:
                style = child.get("style", "")
                style = ";".join(part for part in style.split(";") if not part.startswith("display:"))
                child.set("style", style + (";display:inline" if child is selected else ";display:none"))
    return ET.tostring(root)


@lru_cache(maxsize=128)
def svg_bytes(path: str, modified: int) -> bytes:
    return Path(path).read_bytes()


def renderer_for(path: Path, parent=None) -> QSvgRenderer:
    return QSvgRenderer(QByteArray(svg_bytes(str(path), path.stat().st_mtime_ns)), parent)


def resolve_artwork(model: ControllerDefinition, custom: str | None = None) -> Path | None:
    candidates = []
    if custom:
        if custom.startswith("asset:"):
            candidates.append(ASSET_DIR / Path(custom[6:]).name)
        elif custom.startswith("user:"):
            candidates.append(DATA_DIR / "illustrations" / Path(custom[5:]).name)
        else:
            candidates.append(Path(custom))  # Existing absolute-path preferences.
    if model.svg:
        candidates.append(ASSET_DIR / model.svg)
    candidates.append(ASSET_DIR / (model.family + ".svg"))
    candidates.append(ASSET_DIR / "library-generic.svg")
    candidates.append(ASSET_DIR / "generic.svg")
    for path in candidates:
        try:
            if path.is_file() and renderer_for(path).isValid():
                return path
        except OSError:
            continue
    return None


class SvgView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.renderer = QSvgRenderer(self)
        self.render_scale = 1.0
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def set_path(self, path: Path | None):
        self.renderer.load(QByteArray(path.read_bytes()) if path else QByteArray())
        self.update()

    def set_render_scale(self, scale: float):
        if not 0 < scale <= 1:
            raise ValueError("SVG render scale must be between 0 and 1")
        self.render_scale = scale
        self.update()

    def set_prompt(self, labels: list[str]):
        width = max(44, sum(max(44, len(label) * 9 + 16) for label in labels))
        text = escape(" + ".join(labels))
        data = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 36">'
                f'<rect x="1" y="1" width="{width-2}" height="34" rx="12" '
                f'fill="#20527b" stroke="#65baff"/><text x="{width/2}" y="23" '
                f'text-anchor="middle" font-family="Inter 18pt" font-size="12" '
                f'fill="white">{text}</text></svg>')
        self.renderer.load(QByteArray(themed(data).encode("utf-8")))
        self.update()

    def set_controller_prompt(self, trigger: str, model: ControllerDefinition | None):
        buttons = trigger.split("+")
        width = 36 * len(buttons) + 12 * (len(buttons) - 1)
        root = ET.Element("{http://www.w3.org/2000/svg}svg", viewBox=f"0 0 {width} 36")
        sources = []
        for index, logical in enumerate(buttons):
            path = prompt_path(logical, model)
            if path:
                child = ET.fromstring(prompt_svg(str(path)))
                sources.append(str(path.relative_to(ASSET_DIR)))
                # Each prompt has its own IDs. Prefix IDs/references when composing chords.
                ids = {node.get("id"): f"prompt{index}_{node.get('id')}" for node in child.iter() if node.get("id")}
                for node in child.iter():
                    for key, value in list(node.attrib.items()):
                        if key == "id":
                            node.set(key, ids[value])
                        else:
                            for old, new in ids.items():
                                value = value.replace(f"url(#{old})", f"url(#{new})")
                                if value == "#" + old:
                                    value = "#" + new
                            node.set(key, value)
                x, y, w, h = map(float, child.get("viewBox", "0 0 36 36").replace(",", " ").split())
                scale = min(36 / w, 36 / h)
                child.tag = "{http://www.w3.org/2000/svg}g"
                for key in ("width", "height", "viewBox", "version"):
                    child.attrib.pop(key, None)
                child.set("transform", f"translate({index * 48 + (36-w*scale)/2} {(36-h*scale)/2}) "
                          f"scale({scale}) translate({-x} {-y})")
                root.append(child)
            else:
                label = model.physical_labels.get(logical, logical) if model else logical
                if logical == "GUIDE":
                    label = "Guide"  # No platform Guide logos are redistributed.
                text = ET.SubElement(root, "{http://www.w3.org/2000/svg}text", {
                    "x": str(index * 48 + 18), "y": "22", "text-anchor": "middle",
                    "font-family": "Inter 18pt", "font-size": str(min(9, 48 / max(len(label), 1))), "fill": "white"})
                text.text = label
            if index:
                plus = ET.SubElement(root, "{http://www.w3.org/2000/svg}text", {
                    "x": str(index * 48 - 6), "y": "23", "text-anchor": "middle",
                    "font-family": "Inter 18pt", "font-size": "16", "fill": "white"})
                plus.text = "+"
        self.setProperty("svgSources", sources)
        self.renderer.load(QByteArray(ET.tostring(root)))
        self.update()

    def paintEvent(self, event):
        if not self.renderer.isValid():
            return
        size = self.renderer.defaultSize()
        size.scale(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        width, height = size.width() * self.render_scale, size.height() * self.render_scale
        rect = QRectF((self.width()-width)/2, (self.height()-height)/2, width, height)
        painter = QPainter(self)
        self.renderer.render(painter, rect)
