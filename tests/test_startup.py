import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

from pawz import APP_NAME
from pawz.core.models import Settings
from pawz.infra import startup


def test_startup_command_uses_package_entrypoint_for_python(monkeypatch):
    monkeypatch.delattr(startup.sys, "frozen", raising=False)
    settings = Settings.defaults()
    settings.startup_enabled = True
    settings.start_minimized = True

    assert startup.startup_command(settings) == subprocess.list2cmdline(
        [sys.executable, "-m", "pawz", "--minimized"]
    )


def test_startup_command_uses_executable_when_frozen(monkeypatch):
    monkeypatch.setattr(startup.sys, "frozen", True, raising=False)
    settings = Settings.defaults()
    settings.startup_enabled = True

    assert startup.startup_command(settings) == subprocess.list2cmdline([sys.executable])


def fake_registry():
    key = object()
    handle = MagicMock()
    handle.__enter__.return_value = key
    registry = SimpleNamespace(
        HKEY_CURRENT_USER=1, KEY_SET_VALUE=2, REG_SZ=3,
        CreateKeyEx=Mock(return_value=handle), OpenKey=Mock(return_value=handle),
        SetValueEx=Mock(), DeleteValue=Mock(side_effect=FileNotFoundError),
    )
    return registry, key


def test_configure_startup_registers_command_for_current_user(monkeypatch):
    registry, key = fake_registry()
    monkeypatch.setitem(sys.modules, "winreg", registry)
    monkeypatch.setattr(startup, "os", SimpleNamespace(name="nt"))
    settings = Settings.defaults()
    settings.startup_enabled = True

    startup.configure_startup(settings)

    registry.CreateKeyEx.assert_called_once_with(
        1, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, 2
    )
    registry.SetValueEx.assert_called_once_with(
        key, APP_NAME, 0, 3, startup.startup_command(settings)
    )
    # The entry left under the previous name is removed.
    registry.DeleteValue.assert_called_once_with(key, "squidz")


def test_configure_startup_removes_existing_registration(monkeypatch):
    registry, key = fake_registry()
    monkeypatch.setitem(sys.modules, "winreg", registry)
    monkeypatch.setattr(startup, "os", SimpleNamespace(name="nt"))

    startup.configure_startup(Settings.defaults())

    assert [c.args for c in registry.DeleteValue.call_args_list] == [
        (key, "squidz"), (key, APP_NAME)]
