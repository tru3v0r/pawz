"""Refresh the translation files after interface strings change.

    python scripts/update-translations.py            # extract, then compile
    python scripts/update-translations.py --new de   # also start a German file

1. ``pyside6-lupdate`` scans every ``tr()`` / ``QT_TR_NOOP()`` call under
   ``src/pawz`` and updates ``src/pawz/data/i18n/pawz_<lang>.ts``: new strings
   are added as unfinished, removed ones are marked obsolete and dropped.
2. Translate the unfinished entries (Qt Linguist, or any text editor).
3. Run the script again: ``pyside6-lrelease`` compiles each ``.ts`` to the
   ``.qm`` file the application loads.

To offer a new language, run with ``--new <code>``, translate the file, then add
the code to ``LANGUAGES`` in ``src/pawz/i18n.py``.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import PySide6

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "pawz"
TRANSLATIONS = PACKAGE / "data" / "i18n"
TOOLS = Path(PySide6.__file__).parent


def tool(name: str) -> str:
    path = TOOLS / (name + ".exe" if sys.platform == "win32" else name)
    return str(path if path.exists() else name)


def sources() -> list[str]:
    return sorted(str(path) for path in PACKAGE.rglob("*.py"))


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
    for ts in files:
        language = ts.stem.removeprefix("pawz_")
        subprocess.run([tool("lupdate"), *sources(), "-no-obsolete", "-locations", "none",
                        "-source-language", "en", "-target-language", language,
                        "-ts", str(ts)], check=True)
        subprocess.run([tool("lrelease"), str(ts), "-qm", str(ts.with_suffix(".qm"))], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
