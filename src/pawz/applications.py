"""Applications pawz knows, from ``data/applications/applications.json``: display
names, browsers (website shortcuts), applications never put in game mode, and where
to find an executable for its icon."""
from __future__ import annotations

from pathlib import PurePath

from pawz import APP_ID, data_files

_KNOWN: dict[str, dict] = data_files.load("applications/applications.json")["applications"]

BROWSER_PROCESSES = tuple(app for app, info in _KNOWN.items() if info.get("browser"))
# pawz itself is never a game either.
NEVER_GAMES = frozenset({APP_ID + ".exe", *(app for app, info in _KNOWN.items() if info.get("never_game"))})


def display_name(executable: str) -> str:
    """The application's name, or its executable without ``.exe``."""
    return _KNOWN.get(executable.lower(), {}).get("name") or PurePath(executable).stem


def install_paths(executable: str) -> tuple[str, ...]:
    """Where the executable usually is, relative to the program folders."""
    return tuple(_KNOWN.get(executable.lower(), {}).get("install_paths", ()))
