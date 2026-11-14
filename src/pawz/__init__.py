"""pawz: control Windows with a game controller.

The application's identity lives here. Renaming the application means changing
these constants, the package folder (Python import name) and the documentation.
"""
import os

APP_NAME = "pawz"  # shown to the user
APP_ID = "pawz"  # settings folder, startup entry, identifiers
APP_VERSION = "0.1.0"  # keep in step with pyproject.toml
PREVIOUS_IDS = ("squidz",)  # earlier names: settings and startup entry are migrated
ENV_PREFIX = APP_ID.upper() + "_"  # PAWZ_DATA_DIR, PAWZ_MAGNET_TRACE...


def env(name: str, default: str | None = None) -> str | None:
    """Value of the ``<ENV_PREFIX><name>`` environment variable."""
    return os.environ.get(ENV_PREFIX + name, default)


# SOUTH/EAST/WEST/NORTH are positions everywhere in the app (catalog, bindings).
# By default SDL reports Nintendo face buttons by their printed label instead, so
# A (on the right) would arrive as SOUTH. Ask for positions before SDL starts.
os.environ.setdefault("SDL_GAMECONTROLLER_USE_BUTTON_LABELS", "0")
