"""When pawz steps aside and leaves the controller to a game.

Pure decision: the caller supplies the foreground application and whether it
covers its whole monitor. In game mode pawz sends nothing (no pointer, no
clicks, no shortcuts) except the action that toggles game mode itself.

Rules, by priority
1. A manual toggle (``override``) wins, as long as the same application stays in
   the foreground.
2. Applications listed in ``games`` are always games, those in ``non_games`` (and
   ``NEVER_GAMES``: browsers, video players, the desktop) never.
3. Otherwise, with ``auto`` on, a full-screen application is a game.
"""
from __future__ import annotations

from collections.abc import Collection

from pawz.applications import NEVER_GAMES  # "never_game" in data/applications


def is_game(app: str, fullscreen: bool, *, auto: bool, games: Collection[str],
            non_games: Collection[str], override: tuple[str, bool] | None = None) -> bool:
    app = app.lower()
    if override is not None and override[0] == app:
        return override[1]
    if app in games:
        return True
    if app in non_games or app in NEVER_GAMES or not app:
        return False
    return auto and fullscreen
