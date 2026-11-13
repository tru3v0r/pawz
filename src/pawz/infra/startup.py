"""Windows startup registration."""
import os
import subprocess
import sys

from pawz import APP_NAME, PREVIOUS_IDS
from pawz.core.models import Settings

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = APP_NAME
PREVIOUS_VALUE_NAMES = PREVIOUS_IDS


def startup_command(settings: Settings) -> str:
    if getattr(sys, "frozen", False):
        command = [sys.executable]
    else:
        command = [sys.executable, "-m", __package__.split(".")[0]]
    if settings.startup_enabled and settings.start_minimized:
        command.append("--minimized")
    return subprocess.list2cmdline(command)


def _remove_previous_entries(winreg) -> None:
    """Entries left by the application under a previous name."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            for name in PREVIOUS_VALUE_NAMES:
                try:
                    winreg.DeleteValue(key, name)
                except FileNotFoundError:
                    pass
    except FileNotFoundError:
        pass


def configure_startup(settings: Settings) -> None:
    if os.name != "nt":
        raise OSError("Windows startup registration is only available on Windows")

    import winreg

    _remove_previous_entries(winreg)
    if settings.startup_enabled:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, startup_command(settings))
        return

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except FileNotFoundError:
        pass
