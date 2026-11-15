import pytest

from pawz.ui import artwork_styles, controller_assets, themes


@pytest.fixture(autouse=True)
def source_theme():
    """Tests read the source (Corporate Blue) colours and unstyled controller artwork;
    main() and the settings dialog may select others."""
    themes.set_current(themes.CORPORATE_BLUE)
    artwork_styles.set_current(artwork_styles.ORIGINAL)
    yield
    themes.set_current(themes.CORPORATE_BLUE)
    artwork_styles.set_current(artwork_styles.ORIGINAL)


@pytest.fixture(autouse=True)
def no_user_artwork(tmp_path_factory, monkeypatch):
    """Renamed copies the user saved with Name inputs must not leak into tests."""
    monkeypatch.setattr(controller_assets, "OVERRIDES_DIR", tmp_path_factory.mktemp("artwork"))
