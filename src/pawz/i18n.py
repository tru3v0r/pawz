"""Interface language: translation lookup and loading.

Source strings are English and wrapped in ``tr()``; translations are Qt Linguist
files (``data/i18n/pawz_<lang>.ts``) compiled to ``.qm`` with
``scripts/update-translations.py``. ``pyside6-lupdate`` extracts every
``tr("...")`` call, so the text must be a literal: use ``tr("{n} items").format(...)``,
never an f-string. Strings defined at import time are marked with ``QT_TR_NOOP()``
(a no-op lupdate recognizes, also defined locally in Qt-free modules) and passed
through ``tr()`` where they are displayed.

Arabic and Sorani Kurdish lay the interface out right to left. The language is
applied at startup; changing it in Settings takes effect on restart.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QLibraryInfo, QLocale, Qt, QTranslator

from pawz import data_files

TRANSLATIONS_DIR = Path(__file__).resolve().parent / "data" / "i18n"
# Qt's own dialog buttons (OK, Cancel, Yes, No, Save) for the languages Qt ships no
# qtbase translation for: {code: {English text: translation}}.
BUTTONS_FILE = TRANSLATIONS_DIR / "qt_buttons.json"
AUTO = "auto"
# Languages, qualities, varieties: data/i18n/languages.json.
_DATA = data_files.load("i18n/languages.json")
SOURCE_LANGUAGE: str = _DATA["source"]
# Languages offered in Settings, each named in its own language, sorted by that name.
LANGUAGES = dict(sorted(((code, info["name"]) for code, info in _DATA["languages"].items()),
                        key=lambda item: item[1].casefold()))
RIGHT_TO_LEFT = {code for code, info in _DATA["languages"].items() if info.get("right_to_left")}
# Qt locale (number and date formats) for codes Qt does not know.
_QT_LOCALES = {code: info["qt_locale"] for code, info in _DATA["languages"].items() if "qt_locale" in info}
_ALIASES: dict[str, str] = _DATA["aliases"]  # other codes a system may report
_VARIETIES: dict[str, dict] = _DATA["varieties"]
_installed: list[QTranslator] = []


def tr(text: str, disambiguation: str | None = None, n: int = -1) -> str:
    """Translate ``text`` into the interface language (``%n`` takes ``n``)."""
    return QCoreApplication.translate("", text, disambiguation, n)


def QT_TR_NOOP(text: str) -> str:  # name pyside6-lupdate looks for
    """Mark a string for extraction without translating it yet."""
    return text


# Estimated quality of each translation (machine translations no native speaker has
# reviewed yet, French excepted): Settings shows it and invites speakers to improve them.
EXCELLENT = "excellent"
QUALITY = {code: info["quality"] for code, info in _DATA["languages"].items() if "quality" in info}
QUALITY_NAMES = {level: info["label"] for level, info in _DATA["qualities"].items()}
QUALITY_SENTENCES = {level: info["sentence"] for level, info in _DATA["qualities"].items()}
TRANSLATIONS_URL: str = _DATA["translations_url"]


def quality_note(code: str) -> str:
    """What Settings says under the language picker about ``code``'s translation
    (rich text, in the interface language), or "" for the source language."""
    quality = QUALITY.get(code)
    if quality is None:
        return ""
    note = tr(QUALITY_SENTENCES[quality])
    if quality != EXCELLENT:
        invitation = tr('If you speak this language, you can help improve its translation on the <a href="{url}">pawz GitHub repository</a>.')
        note += "<br>" + invitation.format(url=TRANSLATIONS_URL)
    return note


def match(name: str) -> str | None:
    """The offered language for a system language tag such as ``es-MX``,
    ``zh-Hant-HK`` or ``ku-Arab-IQ``, or None."""
    parts = name.replace("-", "_").split("_")
    language = _ALIASES.get(parts[0].lower(), parts[0].lower())
    script = next((part.title() for part in parts[1:] if len(part) == 4), "")
    region = next((part.upper() for part in parts[1:] if len(part) in (2, 3) and part != parts[0]), "")
    variety = _VARIETIES.get(language)
    if variety is not None:
        return (variety.get("scripts", {}).get(script) or variety.get("regions", {}).get(region)
                or variety["default"])
    return language if language in LANGUAGES else None


def resolve(language: str, system: QLocale | None = None) -> str:
    """The language actually used: ``auto`` follows Windows when it is supported."""
    if language in LANGUAGES:
        return language
    for name in (system or QLocale.system()).uiLanguages():
        if code := match(name):
            return code
    return SOURCE_LANGUAGE


class _ButtonTranslator(QTranslator):
    """Qt's standard button texts from ``qt_buttons.json``."""

    def __init__(self, texts: dict[str, str], parent=None):
        super().__init__(parent)
        self.texts = texts

    def translate(self, context, source, disambiguation=None, n=-1):
        # None, not "", tells Qt the text is not here, so it keeps looking.
        return self.texts.get(source) if context == "QPlatformTheme" else None

    def isEmpty(self) -> bool:
        return not self.texts


def button_texts(code: str) -> dict[str, str]:
    try:
        return json.loads(BUTTONS_FILE.read_text(encoding="utf-8")).get(code, {})
    except (OSError, ValueError):
        return {}


def install(app: QCoreApplication, language: str) -> str:
    """Load the translations for ``language`` (or ``auto``); returns the code used."""
    for translator in _installed:
        app.removeTranslator(translator)
    _installed.clear()
    code = resolve(language)
    QLocale.setDefault(QLocale(_QT_LOCALES.get(code, code)))
    if hasattr(app, "setLayoutDirection"):
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft if code in RIGHT_TO_LEFT
                               else Qt.LayoutDirection.LeftToRight)
    if code != SOURCE_LANGUAGE:
        translator = QTranslator(app)
        if translator.load(f"pawz_{code}", str(TRANSLATIONS_DIR)):
            app.installTranslator(translator)
            _installed.append(translator)
        qt = QTranslator(app)
        qt_dir = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        # Loading falls back from qtbase_es_419 to qtbase_es; pt_PT has no fallback.
        if code == "pt_PT" or not qt.load(f"qtbase_{code}", qt_dir):
            qt = _ButtonTranslator(button_texts(code), app)
        if not qt.isEmpty():
            app.installTranslator(qt)
            _installed.append(qt)
    return code
