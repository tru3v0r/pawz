import pytest

from pawz.ui import themes


@pytest.fixture(autouse=True)
def source_theme():
    """Tests read the source (Midnight Blue) colours; main() selects the default theme."""
    themes.set_current(themes.MIDNIGHT_BLUE)
    yield
    themes.set_current(themes.MIDNIGHT_BLUE)
