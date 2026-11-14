import pytest

from pawz.ui import artwork_styles, themes


@pytest.fixture(autouse=True)
def source_theme():
    """Tests read the source (Midnight Blue) colours and unstyled controller artwork;
    main() and the settings dialog may select others."""
    themes.set_current(themes.MIDNIGHT_BLUE)
    artwork_styles.set_current(artwork_styles.ORIGINAL)
    yield
    themes.set_current(themes.MIDNIGHT_BLUE)
    artwork_styles.set_current(artwork_styles.ORIGINAL)
