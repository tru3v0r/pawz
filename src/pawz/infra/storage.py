"""Atomic settings persistence outside the executable directory."""
import json
import os
import secrets
import shutil
from pathlib import Path

from pawz import APP_ID, PREVIOUS_IDS, env
from pawz.core.models import Settings

APPDATA = Path(os.environ.get("APPDATA", str(Path.home() / ".config")))
DATA_DIR = Path(env("DATA_DIR") or APPDATA / APP_ID)
SETTINGS_PATH = DATA_DIR / "settings.json"


def migrate_previous_data(data_dir: Path = DATA_DIR, appdata: Path = APPDATA) -> Path | None:
    """First start under a new name: copy the settings folder of a previous name."""
    if (data_dir / "settings.json").exists():
        return None
    for previous in PREVIOUS_IDS:
        source = appdata / previous
        if (source / "settings.json").is_file():
            shutil.copytree(source, data_dir, dirs_exist_ok=True)
            return source
    return None


def load(path: Path = SETTINGS_PATH) -> Settings:
    if path == SETTINGS_PATH:
        migrate_previous_data()
    if not path.exists():
        obj = Settings.defaults()
        obj.browser_token = secrets.token_urlsafe(32)
        save(obj, path)
        return obj
    payload = path.read_text(encoding="utf-8")
    raw = json.loads(payload)
    obj = Settings.parse(raw)
    if raw.get("schema_version") != Settings.SCHEMA_VERSION:
        backup = path.with_suffix(path.suffix + ".v1.bak")
        if not backup.exists():
            with backup.open("x", encoding="utf-8") as stream:
                stream.write(payload)
        save(obj, path)
    if not obj.browser_token:
        obj.browser_token = secrets.token_urlsafe(32)
        save(obj, path)
    return obj

def save(settings: Settings, path: Path = SETTINGS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(settings.dump(), f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
