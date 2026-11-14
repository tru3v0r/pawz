"""Interface language: translation lookup and loading.

Source strings are English and wrapped in ``tr()``; translations are Qt Linguist
files (``data/i18n/pawz_<lang>.ts``) compiled to ``.qm`` with
``scripts/update-translations.py``. ``pyside6-lupdate`` extracts every
``tr("...")`` call, so the text must be a literal: use ``tr("{n} items").format(...)``,
never an f-string. Strings defined at import time are marked with ``QT_TR_NOOP()``
(a no-op lupdate recognizes, also defined locally in Qt-free modules) and passed
through ``tr()`` where they are displayed.

The language is applied at startup; changing it in Settings takes effect on restart.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QLibraryInfo, QLocale, QTranslator

TRANSLATIONS_DIR = Path(__file__).resolve().parent / "data" / "i18n"
AUTO = "auto"
SOURCE_LANGUAGE = "en"
# Languages offered in Settings, each named in its own language.
LANGUAGES = {"en": "English", "fr": "Français"}
_installed: list[QTranslator] = []


def tr(text: str, disambiguation: str | None = None, n: int = -1) -> str:
    """Translate ``text`` into the interface language (``%n`` takes ``n``)."""
    return QCoreApplication.translate("", text, disambiguation, n)


def QT_TR_NOOP(text: str) -> str:  # name pyside6-lupdate looks for
    """Mark a string for extraction without translating it yet."""
    return text


def resolve(language: str, system: QLocale | None = None) -> str:
    """The language actually used: ``auto`` follows Windows when it is supported."""
    if language in LANGUAGES:
        return language
    for name in (system or QLocale.system()).uiLanguages():
        code = name.replace("-", "_").split("_")[0].lower()
        if code in LANGUAGES:
            return code
    return SOURCE_LANGUAGE


def install(app: QCoreApplication, language: str) -> str:
    """Load the translations for ``language`` (or ``auto``); returns the code used."""
    for translator in _installed:
        app.removeTranslator(translator)
    _installed.clear()
    code = resolve(language)
    QLocale.setDefault(QLocale(code))
    if code != SOURCE_LANGUAGE:
        qt_dir = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        for name, folder in ((f"pawz_{code}", str(TRANSLATIONS_DIR)), (f"qtbase_{code}", qt_dir)):
            translator = QTranslator(app)
            if translator.load(name, folder):
                app.installTranslator(translator)
                _installed.append(translator)
    return code
