"""Application composition root."""
import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from pawz import APP_NAME, env, i18n
from pawz.core.controllers import ControllerManager
from pawz.infra.browser import BrowserBridge
from pawz.infra.debug_events import ETW_HELPER_FLAG
from pawz.infra.etw_helper import main as etw_helper_main
from pawz.infra.startup import configure_startup
from pawz.infra.storage import load
from pawz.ui import artwork_styles, themes
from pawz.ui.windows import CSS, RESTART_FLAG, MainWindow, load_fonts, stylesheet


def wait_for_previous_instance(argv: list[str]) -> None:
    """After a restart, wait until the instance that launched us has exited (it
    holds the browser bridge port), then drop the flag from ``argv``."""
    if RESTART_FLAG not in argv:
        return
    index = argv.index(RESTART_FLAG)
    pid = argv[index + 1] if index + 1 < len(argv) else ""
    del argv[index:index + 2]
    import psutil
    try:
        psutil.Process(int(pid)).wait(timeout=15)
    except (ValueError, psutil.Error):
        pass  # already gone, or not ours to wait for


def main():
    if sys.argv[1:2] == [ETW_HELPER_FLAG]:
        return etw_helper_main(sys.argv[2:])
    if os.name != "nt":
        raise SystemExit(f"{APP_NAME} requires Windows 10/11")
    wait_for_previous_instance(sys.argv)
    app = QApplication(sys.argv)
    load_fonts()
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(CSS)
    smoke_report = env("SMOKE_REPORT")
    try:
        settings = load()
        i18n.install(app, settings.language)
        themes.set_current(settings.theme)
        artwork_styles.set_current(settings.controller_style)
        app.setStyleSheet(stylesheet())
        try:
            if not smoke_report:
                configure_startup(settings)
        except OSError as exc:
            QMessageBox.warning(None, i18n.tr("{app} — Startup").format(app=APP_NAME), str(exc))
        bridge = BrowserBridge(settings.browser_token, settings.port)
        bridge.start()
        manager = ControllerManager(settings, bridge)
    except Exception as exc:
        QMessageBox.critical(None, APP_NAME, str(exc))
        return 1
    window = MainWindow(settings, manager)
    manager.settings_requested.connect(window.show_for_device)
    manager.error.connect(lambda message: window.statusBar().showMessage(message, 5000))
    app.aboutToQuit.connect(manager.stop)
    manager.start()
    if "--minimized" in sys.argv[1:]:
        window.showMinimized()
    else:
        window.show()
    if settings.debug_window_on_startup:
        window.show_debug_window()
    app.aboutToQuit.connect(bridge.stop)
    app.aboutToQuit.connect(window.debug_window.close)
    if smoke_report:
        from PySide6.QtCore import QSize
        from PySide6.QtGui import QFont, QFontInfo

        from pawz.core.controller_catalog import load_builtin_catalog
        from pawz.ui.controller_assets import ASSET_DIR, SvgView, renderer_for, resolve_artwork
        from pawz.ui.rendering import vector_icon
        catalog = load_builtin_catalog()
        illustration = resolve_artwork(catalog[0])
        def finish_smoke():
            prompt = SvgView(window)
            prompt.set_controller_prompt("SOUTH", catalog[0])
            native_icon = vector_icon("pencil").pixmap(QSize(18, 18), 2.0)
            Path(smoke_report).write_text(json.dumps({
                "started": window.isVisible(), "models": len(catalog),
                "svg_valid": bool(illustration and renderer_for(illustration).isValid()),
                "devices": len(manager.controllers),
                "fonts": {name: QFontInfo(QFont(name, 12)).family()
                          for name in ("Matcha Style", "Inter 18pt")},
                "library_prompt_valid": bool(prompt.renderer.isValid() and prompt.property("svgSources")),
                "vector_icon_native_dpi": (not native_icon.isNull() and native_icon.width() == 36
                                           and native_icon.devicePixelRatio() == 2.0),
                "model_svgs_valid": all(model.svg and (ASSET_DIR / model.svg).is_file()
                                        and renderer_for(ASSET_DIR / model.svg).isValid()
                                        for model in catalog),
            }), encoding="utf-8")
            manager.stop()
            app.quit()
        QTimer.singleShot(1200, finish_smoke)
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
