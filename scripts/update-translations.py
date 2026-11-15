"""Refresh the translation files after interface strings change.

    python scripts/update-translations.py            # extract, then compile
    python scripts/update-translations.py --new de   # also start a German file

1. ``pyside6-lupdate`` scans every ``tr()`` / ``QT_TR_NOOP()`` call under
   ``src/pawz``, and the ``label`` strings of the data files (through a temporary
   stub, see ``pawz.data_files``), and updates
   ``src/pawz/data/i18n/pawz_<lang>.ts``: new strings are added as unfinished,
   removed ones are marked obsolete and dropped.
2. Translate the unfinished entries (Qt Linguist, or any text editor).
3. Run the script again: ``pyside6-lrelease`` compiles each ``.ts`` to the
   ``.qm`` file the application loads.

To offer a new language, run with ``--new <code>``, translate the file, then add
the code to ``LANGUAGES`` in ``src/pawz/i18n.py``.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import PySide6

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "pawz"
TRANSLATIONS = PACKAGE / "data" / "i18n"
TOOLS = Path(PySide6.__file__).parent
# Languages lupdate's table lacks ("lupdate_language" in data/i18n/languages.json): it
# refuses to update their files, so it is given a language it knows (used only for
# plural rules, and pawz has no plural strings) and the real code is put back afterwards.
LUPDATE_STAND_INS = {
    code: info["lupdate_language"]
    for code, info in json.loads((TRANSLATIONS / "languages.json").read_text(encoding="utf-8"))["languages"].items()
    if "lupdate_language" in info}


def tool(name: str) -> str:
    path = TOOLS / (name + ".exe" if sys.platform == "win32" else name)
    return str(path if path.exists() else name)


def sources(stub_folder: Path) -> list[str]:
    """The package's code and a stub marking the data files' labels."""
    sys.path.insert(0, str(PACKAGE.parent))
    from pawz import data_files
    stub = data_files.write_translation_stub(stub_folder / "data_labels.py")
    return [*sorted(str(path) for path in PACKAGE.rglob("*.py")), str(stub)]


def set_language(ts: Path, old: str, new: str) -> None:
    if old != new and ts.exists():
        text = ts.read_text(encoding="utf-8")
        ts.write_text(text.replace(f'language="{old}"', f'language="{new}"', 1), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--new", metavar="LANG", help="create pawz_<LANG>.ts")
    args = parser.parse_args()
    TRANSLATIONS.mkdir(parents=True, exist_ok=True)
    files = sorted(TRANSLATIONS.glob("pawz_*.ts"))
    if args.new:
        new = TRANSLATIONS / f"pawz_{args.new}.ts"
        if new not in files:
            files.append(new)
    stub_folder = Path(tempfile.mkdtemp())
    code = sources(stub_folder)
    for ts in files:
        language = ts.stem.removeprefix("pawz_")
        stand_in = LUPDATE_STAND_INS.get(language, language)
        set_language(ts, language, stand_in)
        try:
            subprocess.run([tool("lupdate"), *code, "-no-obsolete", "-locations", "none",
                            "-source-language", "en", "-target-language", stand_in,
                            "-ts", str(ts)], check=True)
        finally:
            set_language(ts, stand_in, language)
        subprocess.run([tool("lrelease"), str(ts), "-qm", str(ts.with_suffix(".qm"))], check=True)
    shutil.rmtree(stub_folder, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
