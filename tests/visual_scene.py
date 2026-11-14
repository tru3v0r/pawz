"""Deterministic UI scenes for screenshot regression tests (no input injection)."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QObject, Signal
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QScrollArea

from pawz.core.models import Settings
from pawz.ui import windows


class SceneManager(QObject):
    devices_changed = Signal()
    controller_button_event = Signal(str, str, bool)


def capture(destination: Path):
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(windows.CSS)
    windows.load_fonts()
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        windows.DATA_DIR = Path(temporary)
        windows.save = lambda _settings: None
        settings = Settings.defaults()
        settings.browser_token = "visual-scene"
        settings.duplicate_profile("Default", "Invité")
        settings.known_devices = {
            "first": "Xbox One", "second": "Nintendo Switch Pro Controller",
            "third": "DualSense",
        }
        settings.device_preferences = {
            "first": {"model_id": "microsoft.xbox-one"},
            "second": {"model_id": "nintendo.switch-pro", "name": "Battletron Pro Controller"},
            "third": {"model_id": "sony.dualsense"},
        }
        settings.primary_device = "first"
        manager = SceneManager()
        manager.controllers = {key: SimpleNamespace(name=name) for key, name in
                               list(settings.known_devices.items())[:2]}
        manager.power_levels = {"first": "full", "second": "medium"}
        manager.joysticks = {}
        dialog = windows.SettingsDialog(settings, controller_manager=manager)
        dialog.resize(820, 760)
        dialog.show()
        for name, index, profile in (("general", 0, "Default"),
                                      ("profiles-default", 2, "Default"),
                                      ("profiles-custom", 2, "Invité"),
                                      ("controllers", 3, "Invité")):
            dialog.tabs.setCurrentIndex(index)
            dialog.profile_picker.setCurrentText(profile)
            QTest.qWait(100)
            app.processEvents()
            dialog.grab().save(str(destination / (name + ".png")))
            if name == "profiles-default":
                scroll = dialog.profile_editor.findChild(QScrollArea, "profileScroll")
                section = next(section for section in dialog.profile_editor.findChildren(windows.ProfileSectionFrame)
                               if section.findChild(QLabel, "profileSectionTitle").text() == "VLC")
                scroll.verticalScrollBar().setValue(section.y())
                QTest.qWait(50)
                dialog.grab().save(str(destination / "profiles-contexts.png"))
                scroll.verticalScrollBar().setValue(0)
            elif name == "controllers":
                scroll = dialog.controllers_page.findChild(QScrollArea, "controllersScroll")
                scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
                QTest.qWait(50)
                dialog.grab().save(str(destination / "controllers-mappings.png"))
        dialog.close()
        window = windows.MainWindow(settings, manager)
        window.show()
        for slot in window.slots:
            slot.battery_animation.stop()
            slot.battery_bar.setValue(60)
        QTest.qWait(100)
        app.processEvents()
        window.grab().save(str(destination / "main.png"))
        window.tray.hide()
        window._battery_timer.stop()
        window.close()
        window.debug_window.close()
    (destination / "environment.json").write_text(json.dumps({
        "qt": __import__("PySide6").__version__,
        "platform": app.platformName(), "scale": os.environ.get("QT_SCALE_FACTOR", "1"),
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    capture(args.destination)
