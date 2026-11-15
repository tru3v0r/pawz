import pytest

from pawz.core.models import Binding, Profile, Settings


def test_defaults():
    settings = Settings.defaults()
    assert list(settings.profiles) == ["Default"]
    p = settings.profiles['Default']
    assert p.resolve('b').action == 'left_click'
    assert p.resolve('a').action == 'right_click'
    assert (p.resolve('y').action, p.resolve('y').keys) == ('key_combo', 'ctrl+c')
    assert (p.resolve('x').action, p.resolve('x').keys) == ('key_combo', 'ctrl+v')
    assert p.resolve('right_stick').action == 'middle_click'
    assert p.resolve('l', 'firefox.exe').action == 'tab_previous'
    assert p.resolve('b', 'brave.exe', 'youtube.com').action == 'left_click'
    assert p.resolve('x', 'firefox.exe', 'www.youtube.com').action == 'play_pause'
    assert p.resolve('y', 'brave.exe', 'm.youtube.com').action == 'fullscreen'
    # VLC uses the same video buttons as YouTube, subtitles on the left stick click.
    assert p.resolve('x', 'vlc.exe').action == 'play_pause'
    assert p.resolve('y', 'vlc.exe').action == 'fullscreen'
    assert p.resolve('left_stick', 'vlc.exe').action == 'key_combo'
    assert p.resolve('left_stick', 'vlc.exe').keys == 'v'
    assert p.resolve('left_stick', 'firefox.exe', 'youtube.com').action == 'subtitles'
    assert p.resolve('a+l', 'brave.exe').action == 'none'
    assert {
        button: (p.resolve(button).action, p.resolve(button).keys)
        for button in ("dpad_up", "dpad_down", "dpad_left", "dpad_right")
    } == {
        "dpad_up": ("key_combo", "up"),
        "dpad_down": ("key_combo", "down"),
        "dpad_left": ("key_combo", "left"),
        "dpad_right": ("key_combo", "right"),
    }


def test_controller_combo_triggers_parse_and_resolve_in_canonical_order():
    profile = Profile.parse("Default", {
        "apps": {"brave.exe": {"l+a": {"action": "tab_previous"}}}
    })

    assert profile.resolve("a+l", "brave.exe").action == "tab_previous"
    assert "SOUTH+LEFT_SHOULDER" in profile.bindings_for("brave.exe")
    with pytest.raises(ValueError, match="Unknown controller button"):
        Profile.parse("Default", {"global_bindings": {"a+unknown": "left_click"}})


def test_legacy_bindings_migrate_without_changing_actions_or_contexts():
    raw = {"schema_version": 1, "profiles": {"Default": {
        "global_bindings": {"a": "left_click", "b": "right_click"},
        "apps": {"vlc.exe": {"l+a": "play_pause"}},
        "sites": {"youtube.com": {"b": "subtitles"}},
    }, "Guest": {"global_bindings": {"y": "win"}}}, "assignments": {"device": "Guest"}}
    migrated = Settings.parse(raw)
    assert migrated.profiles["Default"].resolve("SOUTH").action == "left_click"
    assert migrated.profiles["Default"].resolve("SOUTH+LEFT_SHOULDER", "vlc.exe").action == "play_pause"
    assert migrated.profiles["Default"].resolve("EAST", domain="youtube.com").action == "subtitles"
    assert migrated.assignments == {"device": "Guest"}
    assert Settings.parse(migrated.dump()).dump() == migrated.dump()


def test_roundtrip():
    original = Settings.defaults()
    assert Settings.parse(original.dump()).dump() == original.dump()


def test_default_assigned_profile_roundtrip_and_validation():
    original = Settings.defaults()
    original.profiles["Other"] = Profile("Other")
    original.default_profile = "Other"

    parsed = Settings.parse(original.dump())

    assert parsed.default_profile == "Other"
    raw = original.dump()
    raw["default_profile"] = "Missing"
    with pytest.raises(ValueError, match="default profile"):
        Settings.parse(raw)

def test_legacy_profile_defaults_magnet_strength():
    raw = Settings.defaults().dump()
    raw["profiles"]["Default"].pop("magnet_strength")
    assert Settings.parse(raw).profiles["Default"].magnet_strength == 50

def test_youtube_subtitle_override_is_preserved():
    raw = Settings.defaults().dump()
    raw["profiles"]["Default"]["sites"]["youtube.com"]["b"] = {"action": "subtitles"}
    profile = Settings.parse(raw).profiles["Default"]
    assert "b" not in profile.sites["youtube.com"]
    assert profile.resolve("b", domain="youtube.com").action == "subtitles"

def test_startup_settings_roundtrip_and_legacy_defaults():
    original = Settings.defaults()
    original.startup_enabled = True
    original.start_minimized = True
    original.debug_window_on_startup = True
    assert Settings.parse(original.dump()).start_minimized is True
    assert Settings.parse(original.dump()).debug_window_on_startup is True
    legacy = original.dump()
    legacy.pop("startup_enabled")
    legacy.pop("start_minimized")
    legacy.pop("debug_window_on_startup")
    assert Settings.parse(legacy).startup_enabled is False
    assert Settings.parse(legacy).debug_window_on_startup is False

@pytest.mark.parametrize(
    "name", ["startup_enabled", "start_minimized", "debug_window_on_startup"])
def test_reject_invalid_startup_setting(name):
    raw = Settings.defaults().dump()
    raw[name] = "true"
    with pytest.raises(ValueError, match="Startup options"):
        Settings.parse(raw)

def test_primary_device_roundtrip():
    original = Settings.defaults()
    original.primary_device = "controller-guid#0"
    assert Settings.parse(original.dump()).primary_device == original.primary_device

def test_primary_device_defaults_for_existing_settings():
    original = Settings.defaults().dump()
    original.pop("primary_device")
    assert Settings.parse(original).primary_device is None

def test_reject_invalid_primary_device():
    raw = Settings.defaults().dump()
    raw["primary_device"] = 42
    with pytest.raises(ValueError, match="Primary device"):
        Settings.parse(raw)

def test_reject_invalid_action():
    with pytest.raises(ValueError):
        Binding.parse({'action': 'shell_command'})

def test_longest_site_match():
    p = Profile('test', sites={'example.com': {'a': Binding('left_click')}, 'app.example.com': {'a': Binding('right_click')}})
    assert p.resolve('a', domain='app.example.com').action == 'right_click'


def test_magnet_haptics_defaults_on_round_trips_and_is_validated():
    from pawz.core.models import Profile
    assert Profile.parse("Old", {}).magnet_haptics is True  # settings written before the option
    profile = Profile("P", magnet_haptics=False)
    assert Profile.parse("P", profile.dump()).magnet_haptics is False
    with pytest.raises(ValueError, match="magnet_haptics"):
        Profile.parse("Bad", {"magnet_haptics": "yes"})


def test_magnet_modes_default_round_trip_and_migrate_a_disabled_magnet():
    old = Profile.parse("Old", {})
    assert (old.magnet_auto, old.magnet_background) == (True, False)
    profile = Profile("P", magnet_auto=False, magnet_background=True)
    parsed = Profile.parse("P", profile.dump())
    assert (parsed.magnet_auto, parsed.magnet_background) == (False, True)
    # Strength 0 used to mean "off": now off by default but available with the trigger.
    legacy_off = Profile.parse("Off", {"magnet_strength": 0})
    assert (legacy_off.magnet_auto, legacy_off.magnet_strength) == (False, 50)
    with pytest.raises(ValueError, match="magnet_background"):
        Profile.parse("Bad", {"magnet_background": 1})


def test_identity_is_centralized_and_previous_settings_are_migrated(tmp_path):
    from pawz import APP_ID
    from pawz.infra import storage, windows
    from pawz.infra.browser import TOKEN_HEADER
    assert int.from_bytes(b"PAWZ", "big") == windows.INPUT_TAG
    assert f"X-{APP_ID}-Token" == TOKEN_HEADER
    old = tmp_path / "squidz"
    old.mkdir()
    (old / "settings.json").write_text("{}", encoding="utf-8")
    (old / "illustrations").mkdir()
    new = tmp_path / APP_ID
    assert storage.migrate_previous_data(new, tmp_path) == old
    assert (new / "settings.json").read_text(encoding="utf-8") == "{}"
    assert (new / "illustrations").is_dir()
    assert storage.migrate_previous_data(new, tmp_path) is None  # done once


def test_video_shortcuts_seek_with_the_right_stick_sideways():
    profile = Settings.defaults().profiles["Default"]
    for bindings in (profile.apps["vlc.exe"], profile.sites["youtube.com"]):
        assert bindings["RIGHT_STICK_LEFT"] == Binding("key_combo", "left")
        assert bindings["RIGHT_STICK_RIGHT"] == Binding("key_combo", "right")


def test_older_settings_get_new_default_shortcuts_once_without_overwriting():
    raw = Settings.defaults().dump()
    raw.pop("added_defaults")  # saved by an older pawz
    profile = raw["profiles"]["Default"]
    for trigger in ("RIGHT_STICK_LEFT", "RIGHT_STICK_RIGHT"):
        del profile["apps"]["vlc.exe"][trigger]
        del profile["sites"]["youtube.com"][trigger]
    profile["sites"]["youtube.com"]["RIGHT_STICK_LEFT"] = {"action": "play_pause", "keys": ""}
    settings = Settings.parse(raw)
    default = settings.profiles["Default"]
    assert default.apps["vlc.exe"]["RIGHT_STICK_RIGHT"] == Binding("key_combo", "right")
    assert default.sites["youtube.com"]["RIGHT_STICK_LEFT"] == Binding("play_pause")  # kept
    assert "video-stick-seek" in settings.added_defaults
    # Removed afterwards, it does not come back.
    del default.apps["vlc.exe"]["RIGHT_STICK_RIGHT"]
    again = Settings.parse(settings.dump())
    assert "RIGHT_STICK_RIGHT" not in again.profiles["Default"].apps["vlc.exe"]


def test_default_shortcut_files_are_valid_and_cover_their_contexts():
    from pawz.core.models import default_bindings_for, default_shortcuts
    groups = default_shortcuts()
    assert any(not group.apps and not group.sites for group in groups)  # global shortcuts
    assert default_bindings_for(app="VLC.exe")["LEFT_STICK"] == Binding("key_combo", "v")
    assert default_bindings_for(site="youtube.com")["LEFT_STICK"] == Binding("subtitles")
    assert default_bindings_for(app="notepad.exe") == {}
    for group in groups:
        assert set(group.added) <= set(group.bindings)
