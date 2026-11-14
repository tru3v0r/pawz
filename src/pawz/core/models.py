"""Validated, versioned configuration domain model."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from pawz.core.controller_inputs import migrate_legacy_trigger
from pawz.core.controller_services import validate_mapping
from pawz.engine.actions import ACTION_IDS


def QT_TR_NOOP(text: str) -> str:  # user-facing errors, translated by the UI
    return text


BUTTONS = (
    "SOUTH", "EAST", "WEST", "NORTH", "LEFT_SHOULDER", "RIGHT_SHOULDER",
    "LEFT_STICK", "RIGHT_STICK", "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT",
    "DPAD_RIGHT", "BACK", "START", "GUIDE", "MISC1", "PADDLE1", "PADDLE2",
    "PADDLE3", "PADDLE4", "TOUCHPAD", "LEFT_TRIGGER", "RIGHT_TRIGGER",
)
SYSTEM_DEFAULT_PROFILE_ID = "00000000-0000-0000-0000-000000000001"
ACTIONS = ACTION_IDS
DEFAULT_BINDINGS = {"b": "left_click", "a": "right_click", "y": "key_combo", "x": "key_combo", "l": "previous", "r": "next", "minus": "volume_down", "plus": "volume_up", "home": "win", "right_stick": "middle_click",
                    "dpad_up": "key_combo", "dpad_down": "key_combo",
                    "dpad_left": "key_combo", "dpad_right": "key_combo"}
DEFAULT_KEYS = {"dpad_up": "up", "dpad_down": "down",
                     "dpad_left": "left", "dpad_right": "right",
                     "y": "ctrl+c", "x": "ctrl+v"}  # NORTH: copy, WEST: paste
# Editing layer: ZL held, then a button.
EDIT_LAYER = {"LEFT_TRIGGER+SOUTH": "ctrl+z", "LEFT_TRIGGER+EAST": "ctrl+y",
              "LEFT_TRIGGER+NORTH": "ctrl+x", "LEFT_TRIGGER+WEST": "ctrl+a",
              "LEFT_TRIGGER+START": "ctrl+s", "LEFT_TRIGGER+BACK": "backspace",
              "LEFT_TRIGGER+DPAD_UP": "shift+up", "LEFT_TRIGGER+DPAD_DOWN": "shift+down",
              "LEFT_TRIGGER+DPAD_LEFT": "shift+left", "LEFT_TRIGGER+DPAD_RIGHT": "shift+right"}
GAME_MODE_TRIGGER = "BACK+START"
BROWSER_PROCESSES = ("firefox.exe", "brave.exe", "chrome.exe", "msedge.exe")
BROWSER_BINDINGS = {"l": "tab_previous", "r": "tab_next"}
YOUTUBE_BINDINGS = {"x": "play_pause", "y": "fullscreen"}
VLC_BINDINGS = {"a": "play_pause"}


def normalize_trigger(trigger: str) -> str:
    trigger = migrate_legacy_trigger(trigger)
    buttons = trigger.split("+")
    if not buttons or any(button not in BUTTONS for button in buttons):
        raise ValueError(f"Unknown controller button: {trigger!r}")
    if len(set(buttons)) != len(buttons):
        raise ValueError(f"Duplicate controller button: {trigger!r}")
    return "+".join(sorted(buttons, key=BUTTONS.index))

@dataclass
class Binding:
    action: str = "none"
    keys: str = ""

    @classmethod
    def parse(cls, value: Any) -> Binding:
        if isinstance(value, str):
            value = {"action": value}
        if not isinstance(value, dict) or value.get("action", "none") not in ACTIONS:
            raise ValueError(f"Invalid binding: {value!r}")
        return cls(value.get("action", "none"), str(value.get("keys", "")))

def _normalize_bindings(bindings: dict[str, Binding]) -> dict[str, Binding]:
    normalized: dict[str, Binding] = {}
    for trigger, binding in bindings.items():
        key = normalize_trigger(trigger)
        if key in normalized:
            raise ValueError(f"Duplicate controller trigger after migration: {key}")
        normalized[key] = binding
    return normalized


def _parse_apps(raw: dict, key: str) -> list[str]:
    value = raw.get(key, [])
    if not isinstance(value, list) or not all(isinstance(app, str) for app in value):
        raise ValueError(f"{key} must be a list of executable names")
    return [app.strip().lower() for app in value if app.strip()]


def _parse_bool(raw: dict, key: str, default: bool) -> bool:
    value = raw.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


@dataclass
class Profile:
    name: str
    global_bindings: dict[str, Binding] = field(default_factory=dict)
    apps: dict[str, dict[str, Binding]] = field(default_factory=dict)
    sites: dict[str, dict[str, Binding]] = field(default_factory=dict)
    mouse_speed: float = 16.0
    scroll_speed: float = 3.0
    deadzone: float = 0.18
    magnet_strength: float = 50.0
    profile_id: str = ""
    magnet_haptics: bool = True
    magnet_auto: bool = True  # always on; otherwise only while the right trigger is held
    magnet_background: bool = False  # also targets of visible background windows

    def __post_init__(self):
        if not self.profile_id:
            self.profile_id = (
                SYSTEM_DEFAULT_PROFILE_ID if self.name == "Default" else str(uuid4()))
        self.global_bindings = _normalize_bindings(self.global_bindings)
        self.apps = {
            context: _normalize_bindings(bindings)
            for context, bindings in self.apps.items()
        }
        self.sites = {
            context: _normalize_bindings(bindings)
            for context, bindings in self.sites.items()
        }

    @classmethod
    def parse(cls, name: str, raw: dict) -> Profile:
        def parse_map(m):
            if not isinstance(m, dict):
                raise ValueError("Bindings must be a dictionary")
            return _normalize_bindings({k: Binding.parse(v) for k, v in m.items()})
        strength = float(raw.get("magnet_strength", 50))
        auto = _parse_bool(raw, "magnet_auto", True)
        if "magnet_auto" not in raw and strength <= 0:
            # Before the trigger mode, strength 0 meant "magnetism off": keep it off
            # by default, but usable with the trigger.
            strength, auto = 50.0, False
        return cls(name, parse_map(raw.get("global_bindings", {})),
                   {k.lower(): parse_map(v) for k, v in raw.get("apps", {}).items()},
                   {k.lower(): parse_map(v) for k, v in raw.get("sites", {}).items()},
                   float(raw.get("mouse_speed", 16)), float(raw.get("scroll_speed", 3)),
                   float(raw.get("deadzone", .18)), strength,
                   raw.get("profile_id", ""), _parse_bool(raw, "magnet_haptics", True),
                   auto, _parse_bool(raw, "magnet_background", False))

    def resolve(self, button: str, app: str = "", domain: str = "") -> Binding:
        return self.bindings_for(app, domain).get(normalize_trigger(button), Binding())

    def bindings_for(self, app: str = "", domain: str = "") -> dict[str, Binding]:
        bindings = dict(self.global_bindings)
        bindings.update(self.apps.get(app.lower(), {}))
        domain = domain.lower().removeprefix("www.")
        matching = sorted(
            (host for host in self.sites if domain == host or domain.endswith("." + host)),
            key=len)
        for host in matching:
            bindings.update(self.sites[host])
        return bindings

    def dump(self) -> dict:
        return asdict(self) | {"name": self.name}

@dataclass
class Settings:
    SCHEMA_VERSION = 2
    profiles: dict[str, Profile]
    assignments: dict[str, str] = field(default_factory=dict)
    known_devices: dict[str, str] = field(default_factory=dict)
    browser_token: str = ""
    port: int = 8765
    primary_device: str | None = None
    startup_enabled: bool = False
    start_minimized: bool = False
    debug_window_on_startup: bool = False
    default_profile: str = "Default"
    controller_mappings: dict[str, dict[str, Any]] = field(default_factory=dict)
    device_preferences: dict[str, dict[str, Any]] = field(default_factory=dict)
    display_controller_model: str = "generic.sdl-gamecontroller"
    game_mode_auto: bool = True  # full-screen applications are games
    games: list[str] = field(default_factory=list)  # always games
    non_games: list[str] = field(default_factory=list)  # never games
    language: str = "auto"  # "auto" (follow Windows) or a code from pawz.i18n.LANGUAGES

    @classmethod
    def defaults(cls) -> Settings:
        bindings = {k: Binding(v, DEFAULT_KEYS.get(k, ""))
                    for k, v in DEFAULT_BINDINGS.items()}
        bindings.update({k: Binding("key_combo", keys) for k, keys in EDIT_LAYER.items()})
        bindings[GAME_MODE_TRIGGER] = Binding("game_mode")
        apps = {browser: {k: Binding(v) for k, v in BROWSER_BINDINGS.items()}
                for browser in BROWSER_PROCESSES}
        apps["vlc.exe"] = {k: Binding(v) for k, v in VLC_BINDINGS.items()}
        p = Profile("Default", bindings, apps,
                    {"youtube.com": {k: Binding(v) for k, v in YOUTUBE_BINDINGS.items()}})
        return cls({"Default": p})

    @classmethod
    def parse(cls, raw: dict) -> Settings:
        if raw.get("schema_version") not in (1, cls.SCHEMA_VERSION):
            raise ValueError("Unsupported settings schema version")
        raw = deepcopy(raw)
        raw_profiles = dict(raw["profiles"])
        if raw.get("schema_version") == 1:
            for name, profile in raw_profiles.items():
                profile["profile_id"] = (SYSTEM_DEFAULT_PROFILE_ID if name == "Default"
                                         else str(uuid5(NAMESPACE_URL, "squidz:legacy-profile:" + name)))
        profiles = {name: Profile.parse(name, p) for name, p in raw_profiles.items()}
        profile_ids = [profile.profile_id for profile in profiles.values()]
        if len(set(profile_ids)) != len(profile_ids):
            raise ValueError("Profile IDs must be unique")
        if not profiles:
            raise ValueError("At least one profile required")
        assignments = dict(raw.get("assignments", {}))
        if any(v not in profiles for v in assignments.values()):
            raise ValueError("An assignment references a missing profile")
        default_profile = raw.get("default_profile", "Default")
        if default_profile not in profiles:
            raise ValueError("The default profile must exist")
        primary_device = raw.get("primary_device")
        if primary_device is not None and not isinstance(primary_device, str):
            raise ValueError("Primary device must be a device key or null")
        startup_enabled = raw.get("startup_enabled", False)
        start_minimized = raw.get("start_minimized", False)
        debug_window_on_startup = raw.get("debug_window_on_startup", False)
        if (not isinstance(startup_enabled, bool) or not isinstance(start_minimized, bool)
                or not isinstance(debug_window_on_startup, bool)):
            raise ValueError("Startup options must be booleans")
        mappings = raw.get("controller_mappings", {})
        if not isinstance(mappings, dict):
            raise ValueError("Controller mappings must be a dictionary")
        mappings = {key: validate_mapping(mapping) for key, mapping in mappings.items()}
        preferences = raw.get("device_preferences", {})
        if not isinstance(preferences, dict) or any(not isinstance(value, dict) for value in preferences.values()):
            raise ValueError("Device preferences must be dictionaries")
        for value in preferences.values():
            for key in ("guid", "name", "detected_name", "model_id", "svg"):
                if key in value and not isinstance(value[key], str):
                    raise ValueError(f"Device preference {key} must be a string")
        game_mode_auto = _parse_bool(raw, "game_mode_auto", True)
        games, non_games = (_parse_apps(raw, key) for key in ("games", "non_games"))
        return cls(profiles, assignments, dict(raw.get("known_devices", {})),
                   str(raw.get("browser_token", "")), int(raw.get("port", 8765)),
                   primary_device, startup_enabled, start_minimized,
                   debug_window_on_startup, default_profile,
                   mappings,
                   deepcopy(preferences),
                   str(raw.get("display_controller_model", "generic.sdl-gamecontroller")),
                   game_mode_auto, games, non_games,
                   language if isinstance(language := raw.get("language", "auto"), str) else "auto")

    def dump(self) -> dict:
        return {"schema_version": self.SCHEMA_VERSION, "profiles": {k: v.dump() for k, v in self.profiles.items()},
                "assignments": self.assignments, "known_devices": self.known_devices,
                "browser_token": self.browser_token, "port": self.port,
                "primary_device": self.primary_device,
                "startup_enabled": self.startup_enabled,
                "start_minimized": self.start_minimized,
                "debug_window_on_startup": self.debug_window_on_startup,
                "default_profile": self.default_profile,
                "controller_mappings": deepcopy(self.controller_mappings),
                "device_preferences": deepcopy(self.device_preferences),
                "display_controller_model": self.display_controller_model,
                "game_mode_auto": self.game_mode_auto,
                "games": list(self.games), "non_games": list(self.non_games),
                "language": self.language}

    def duplicate_profile(self, name: str, new_name: str) -> Profile:
        self._validate_profile_name(new_name)
        profile = deepcopy(self.profiles[name])
        profile.name, profile.profile_id = new_name, str(uuid4())
        self.profiles[new_name] = profile
        return profile

    def _validate_profile_name(self, name: str) -> None:
        if not name.strip() or name in self.profiles:
            raise ValueError(QT_TR_NOOP("The profile name is empty or already exists."))

    def rename_profile(self, name: str, new_name: str) -> None:
        self._validate_profile_name(new_name)
        profile = self.profiles.pop(name)
        profile.name = new_name
        self.profiles[new_name] = profile
        self.assignments = {key: new_name if value == name else value
                            for key, value in self.assignments.items()}
        if self.default_profile == name:
            self.default_profile = new_name

    def remove_profile(self, name: str) -> None:
        if self.profiles[name].profile_id == SYSTEM_DEFAULT_PROFILE_ID:
            raise ValueError(QT_TR_NOOP("The default system profile cannot be removed."))
        if len(self.profiles) == 1:
            raise ValueError(QT_TR_NOOP("At least one profile is required."))
        del self.profiles[name]
        self.assignments = {key: value for key, value in self.assignments.items() if value != name}
        if self.default_profile == name:
            self.default_profile = next(iter(self.profiles))
