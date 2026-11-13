"""Controller polling on a dedicated input thread, and execution of gesture effects.

Threading model
- ``InputThread`` owns SDL/pygame: it initializes it, polls the controllers at
  ``POLL_HZ`` and injects input. Cursor smoothness no longer depends on the Qt
  event loop.
- The Qt thread owns ``settings``. The input thread only reads ``config``, a
  private copy refreshed by ``sync_settings`` every ``CONFIG_SYNC_MS`` (and right
  after hardware changes), so the UI can mutate settings freely.
- Hardware discoveries flow back through the queued ``_hardware_found`` signal and
  are written into ``settings`` on the Qt thread.
- ``_lock`` serializes polling with ``begin_input_capture``/``end_input_capture``.

Gesture rules (chords, holds, long presses, capture) live in pawz.engine.gestures.
"""
from __future__ import annotations

import threading
import time
from copy import deepcopy

import pygame
from pygame._sdl2 import controller as sdl_controller
from PySide6.QtCore import QObject, QThread, QTimer, Signal

from pawz.core.controller_catalog import ControllerCatalog
from pawz.core.controller_inputs import SDL2_BUTTON_TO_LOGICAL
from pawz.core.controller_services import DeviceIdentityRegistry, read_raw, resolve_model
from pawz.core.models import BROWSER_PROCESSES, Settings, normalize_trigger
from pawz.core.pointer import radial_deadzone
from pawz.engine import actions
from pawz.engine.actions import OutputSink
from pawz.engine.game_mode import is_game
from pawz.engine.gestures import (
    CaptureInput,
    Dispatch,
    Effect,
    GestureEngine,
    LongPress,
    MouseDown,
    MouseUp,
)
from pawz.infra import windows
from pawz.infra.storage import DATA_DIR

POWER_PERCENTAGES = {"empty": 0, "low": 20, "medium": 60, "full": 100, "max": 100}
POLL_HZ = 250
IDLE_POLL_HZ = 20  # no controller connected: only hotplug detection is needed
CONFIG_SYNC_MS = 250
# Haptic cue per magnet event: (low-frequency motor, high-frequency motor, duration ms).
# Capture is a short low "thunk"; release a lighter high-frequency tick.
MAGNET_RUMBLE = {"captured": (0.2, 0.06, 30), "released": (0.0, 0.16, 20)}
# Game mode toggled from the controller: a longer pulse in, a short tick out.
GAME_RUMBLE = {"game_on": (0.35, 0.1, 120), "game_off": (0.0, 0.3, 40)}
GAME_CHECK_S = 0.25
# Held, it turns magnetism on when the profile is not in automatic mode.
MAGNET_TRIGGER = "RIGHT_TRIGGER"


def battery_percentage(power_level: str) -> int | None:
    return POWER_PERCENTAGES.get(power_level.lower())

BUTTON_MAP = {
    index: button.value for index, button in SDL2_BUTTON_TO_LOGICAL.items()
}


class InputThread(QThread):
    """Runs every SDL call and the polling loop off the Qt thread."""

    def __init__(self, manager: ControllerManager):
        super().__init__()
        self.manager = manager
        self.measured_hz = 0.0

    def run(self) -> None:
        manager = self.manager
        try:
            manager.init_sdl()
            with manager._lock:
                manager.refresh()
        except Exception as exc:
            manager.error.emit(f"Initialisation des manettes impossible : {exc}")
            return
        deadline = time.perf_counter()
        window_start, ticks = deadline, 0
        while not self.isInterruptionRequested():
            with manager._lock:
                manager.poll()
            ticks += 1
            now = time.perf_counter()
            if now - window_start >= 1:
                self.measured_hz = ticks / (now - window_start)
                window_start, ticks = now, 0
            deadline += 1 / (POLL_HZ if manager.controllers else IDLE_POLL_HZ)
            delay = deadline - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            else:  # Fell behind (system busy): do not try to catch up in a burst.
                deadline = time.perf_counter()
        with manager._lock:
            manager.release_all()


class ControllerManager(QObject):
    settings_requested = Signal(str)
    devices_changed = Signal()
    error = Signal(str)
    controller_button_event = Signal(str, str, bool)
    _hardware_found = Signal(object)
    game_mode_changed = Signal(bool)
    game_active = False

    def __init__(self, settings: Settings, bridge, *, threaded: bool = True,
                 output: OutputSink | None = None):
        """``threaded=True``: call ``start()`` once signals are connected.
        ``threaded=False`` keeps everything on the caller's thread (tests).
        ``output`` receives every injected input (Windows by default)."""
        super().__init__()
        self.settings, self.bridge = settings, bridge
        self.output: OutputSink = output if output is not None else windows.WindowsOutput()
        self.config: Settings = deepcopy(settings)
        self.identities = DeviceIdentityRegistry()
        self.catalog = ControllerCatalog(DATA_DIR / "controllers" / "catalog.json")
        self.controllers: dict[str, sdl_controller.Controller] = {}
        self.joysticks: dict[str, pygame.joystick.JoystickType] = {}
        self.power_levels: dict[str, str] = {}
        self.gestures = GestureEngine()
        self.game_active = False
        self._game_override: tuple[str, bool] | None = None
        self._game_checked = 0.0
        self.scroll_acc: dict[str, float] = {}
        # (device, stick) pairs seen at rest since the device connected; see _stick().
        self._sticks_at_rest: set[tuple[str, str]] = set()
        # perf_counter: time.monotonic() only advances in ~15.6 ms steps on Windows,
        # which gave 3 ticks out of 4 a zero dt (zero movement) at 250 Hz.
        self.last_poll = time.perf_counter()
        self.last_power_poll = 0.0
        self._lock = threading.RLock()
        self._device_info: dict[str, tuple[str, str]] = {}
        self._mapping_cache: dict[str, dict[str, str]] = {}
        self._mapping_sources: tuple[object, object] = (None, None)
        self._hardware_found.connect(self._apply_hardware)
        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(CONFIG_SYNC_MS)
        self._sync_timer.timeout.connect(self.sync_settings)
        self._sync_timer.start()
        self._thread: InputThread | None = None
        if threaded:
            self._thread = InputThread(self)
        else:
            self.init_sdl()
            self.refresh()

    # -- lifecycle (Qt thread) -------------------------------------------------------

    def start(self) -> None:
        if self._thread is not None and not self._thread.isRunning():
            self._thread.start()

    @staticmethod
    def init_sdl() -> None:
        pygame.init()
        pygame.joystick.init()
        sdl_controller.init()

    def stop(self) -> None:
        """Stop polling and release every held mouse button."""
        self._sync_timer.stop()
        if self._thread is not None:
            self._thread.requestInterruption()
            self._thread.wait(2000)
            self._thread = None
        else:
            with self._lock:
                self.release_all()

    @property
    def poll_rate(self) -> float:
        """Measured polling frequency in Hz (0 until the first second elapses)."""
        return self._thread.measured_hz if self._thread is not None else 0.0

    def sync_settings(self) -> None:
        """Publish a private copy of the settings to the input thread."""
        self.config = deepcopy(self.settings)

    def _apply_hardware(self, found: dict) -> None:
        """Record discovered devices in the live settings (Qt thread)."""
        devices: dict[str, tuple[str, str]] = found["devices"]
        for key, (guid, name) in devices.items():
            self.settings.device_preferences.setdefault(key, {}).update(
                guid=guid, detected_name=name)
            self.settings.known_devices[key] = name
        primary_changed = False
        if devices and self.settings.primary_device not in devices:
            self.settings.primary_device = next(iter(devices))
            primary_changed = True
        self.sync_settings()
        if found["changed"] or primary_changed:
            self.devices_changed.emit()

    # -- hardware (input thread) -------------------------------------------------------

    def refresh(self):
        pygame.event.pump()
        previous = set(self.controllers)
        config = self.config
        discovered = {}
        joysticks = {}
        power_levels = {}
        info: dict[str, tuple[str, str]] = {}
        instance_ids = {pygame.joystick.Joystick(i).get_instance_id()
                        for i in range(pygame.joystick.get_count())}
        self.identities.retain(instance_ids)
        reserved = set(self.identities.instances.values())
        for index in range(pygame.joystick.get_count()):
            joy = pygame.joystick.Joystick(index)
            joy.init()
            controller = sdl_controller.Controller(index) if sdl_controller.is_controller(index) else None
            guid = joy.get_guid()
            key = self.identities.acquire(joy.get_instance_id(), guid,
                                          config.known_devices,
                                          config.device_preferences,
                                          reserved | set(discovered))
            reserved.add(key)
            discovered[key] = controller
            joysticks[key] = joy
            power_levels[key] = joy.get_power_level().lower()
            info[key] = (guid, joy.get_name())
        for device in set(self.gestures.devices) - set(discovered):
            self._apply(self.gestures.remove_device(device))
        self.scroll_acc = {key: value for key, value in self.scroll_acc.items() if key in discovered}
        kept = set(discovered) & previous  # a newly connected device starts unarmed
        self._sticks_at_rest = {pair for pair in self._sticks_at_rest if pair[0] in kept}
        self._device_info = info
        self._mapping_cache = {}
        # Whole-dict replacement: the Qt thread may read these at any time.
        self.controllers = discovered
        self.joysticks = joysticks
        self.power_levels = power_levels
        self._hardware_found.emit({"devices": info, "changed": set(discovered) != previous})

    def release_all(self) -> None:
        for device in list(self.gestures.devices):
            self._apply(self.gestures.remove_device(device))

    def _rumble(self, key: str, event: str) -> None:
        pattern = MAGNET_RUMBLE.get(event) or GAME_RUMBLE.get(event)
        joystick = self.joysticks.get(key)
        if pattern is None or joystick is None:
            return
        try:
            joystick.rumble(*pattern)
        except (pygame.error, AttributeError):
            pass  # Controller without rumble motors, or a pygame build without rumble.

    def _profile(self, key):
        config = self.config
        name = config.assignments.get(key, config.default_profile)
        return config.profiles.get(name) or config.profiles[config.default_profile]

    def _mapping(self, key):
        config, catalog = self.config, self.catalog
        if config is not self._mapping_sources[0] or catalog is not self._mapping_sources[1]:
            self._mapping_cache, self._mapping_sources = {}, (config, catalog)
        if key not in self._mapping_cache:
            preferences = config.device_preferences.get(key, {})
            guid, name = self._device_info.get(
                key, (preferences.get("guid", ""), preferences.get("detected_name", "")))
            model_id = resolve_model(catalog.definitions, guid, name, preferences.get("model_id"))
            self._mapping_cache[key] = {**catalog.get(model_id).hardware_mapping,
                                        **config.controller_mappings.get(key, {})}
        return self._mapping_cache[key]

    def _dispatch(self, device, button):
        try:
            binding = self._binding(device, button)
            if self.game_active and binding.action != "game_mode":
                return  # the controller belongs to the game
            if actions.get(binding.action).internal:
                self._internal_action(device, binding.action)
            else:
                actions.execute(binding.action, binding.keys, self.output)
        except Exception as exc:
            self.error.emit(str(exc))

    def _internal_action(self, device: str, action: str) -> None:
        if action == "open_settings" and device == self.config.primary_device:
            self.settings_requested.emit(device)
        elif action == "game_mode":
            active = not self.game_active
            self._game_override = (windows.active_process(), active)
            self._set_game_mode(active)
            self._rumble(device, "game_on" if active else "game_off")

    def _check_game_mode(self, now: float) -> None:
        if now - self._game_checked < GAME_CHECK_S:
            return
        self._game_checked = now
        app = windows.active_process()
        if self._game_override is not None and self._game_override[0] != app:
            self._game_override = None  # a manual toggle lasts while its app is in front
        config = self.config
        self._set_game_mode(is_game(
            app, windows.foreground_fullscreen(), auto=config.game_mode_auto,
            games=config.games, non_games=config.non_games, override=self._game_override))

    def _set_game_mode(self, active: bool) -> None:
        if active == self.game_active:
            return
        # Held clicks are let go, and buttons still held stay inert until released.
        self._apply(self.gestures.release_clicks())
        self.game_active = active
        self.game_mode_changed.emit(active)

    def _context(self):
        app = windows.active_process()
        return app, self.bridge.domain(app) if app in BROWSER_PROCESSES else ""

    def _binding(self, device, button):
        return self._profile(device).resolve(button, *self._context())

    def _context_bindings(self, device):
        return self._profile(device).bindings_for(*self._context())

    def _actions(self, device) -> dict[str, str]:
        """Action name of every trigger (single buttons and chords) in the current context."""
        return {normalize_trigger(trigger): binding.action
                for trigger, binding in self._context_bindings(device).items()}

    def _apply(self, effects: list[Effect]) -> None:
        for effect in effects:
            try:
                match effect:
                    case Dispatch(device, trigger):
                        self._dispatch(device, trigger)
                    case MouseDown(_, button) if not self.game_active:
                        self.output.mouse_down(button)
                    case MouseUp(_, button) if not self.game_active:
                        self.output.mouse_up(button)
                    case CaptureInput(device, button, pressed):
                        self.controller_button_event.emit(device, button, pressed)
                    case LongPress(device, "GUIDE") if not self.game_active:
                        if device == self.config.primary_device:
                            self.settings_requested.emit(device)
            except Exception as exc:
                self.error.emit(str(exc))

    # -- capture (called from the Qt thread) ---------------------------------------------

    def begin_input_capture(self):
        with self._lock:
            self._apply(self.gestures.begin_capture())

    def end_input_capture(self):
        with self._lock:
            self.gestures.end_capture()

    # -- polling (input thread) -----------------------------------------------------------

    def _press_button(self, device, button, now):
        button = normalize_trigger(button)
        actions: dict[str, str] = {}
        if not self.gestures.capture_active:
            try:
                actions = self._actions(device)
            except Exception as exc:
                self.error.emit(str(exc))
        self._apply(self.gestures.press(device, button, now, actions))

    def _release_button(self, device, button):
        self._apply(self.gestures.release(device, normalize_trigger(button)))

    def _stick(self, key: str, stick: str, x: float, y: float,
               deadzone: float) -> tuple[float, float]:
        """Deadzoned stick position, ignored until the stick has been seen at rest.

        Right after connecting, SDL can report a stale off-center position for a
        Switch Pro controller until the stick physically moves, which drove the
        pointer on its own. A stick only counts once it has been inside the deadzone.
        """
        if (key, stick) not in self._sticks_at_rest:
            if radial_deadzone(x, y, deadzone) != (0.0, 0.0):
                return 0.0, 0.0
            self._sticks_at_rest.add((key, stick))
        return radial_deadzone(x, y, deadzone)

    def poll(self):
        try:
            pygame.event.pump()
            instances = {pygame.joystick.Joystick(i).get_instance_id()
                         for i in range(pygame.joystick.get_count())}
            if instances != set(self.identities.instances):
                self.refresh()
            now = time.perf_counter()
            if self.controllers:
                self._check_game_mode(now)
            dt = min(now - self.last_poll, .05)
            self.last_poll = now
            if now - self.last_power_poll >= 5:
                self.power_levels = {
                    key: joystick.get_power_level().lower()
                    for key, joystick in self.joysticks.items()
                }
                self.last_power_poll = now
            for key, joy in list(self.controllers.items()):
                mapping = self._mapping(key)
                for index, button in BUTTON_MAP.items():
                    source = mapping.get(button)
                    down = (read_raw(self.joysticks[key], source) > .5 if source else
                            bool(joy.get_button(index)) if joy is not None else False)
                    held = self.gestures.is_pressed(key, button)
                    if down and not held:
                        self._press_button(key, button, now)
                    elif not down and held:
                        self._release_button(key, button)
                for logical, index in (("LEFT_TRIGGER", 4), ("RIGHT_TRIGGER", 5)):
                    source = mapping.get(logical)
                    value = (read_raw(self.joysticks[key], source) if source else
                             joy.get_axis(index) / 32767.0 if joy is not None else 0.0)
                    held = self.gestures.is_pressed(key, logical)
                    if value > .5 and not held:
                        self._press_button(key, logical, now)
                    elif value <= .5 and held:
                        self._release_button(key, logical)
                self._apply(self.gestures.tick(key, now))
                if self.game_active:
                    continue  # no pointer or wheel: the game reads the sticks
                p = self._profile(key)
                def axis(n, mapping=mapping, joystick=self.joysticks[key], joy=joy):
                    source = mapping.get(("LEFT_X", "LEFT_Y", "RIGHT_X", "RIGHT_Y")[n])
                    return (read_raw(joystick, source) if source else
                            joy.get_axis(n) / 32767.0 if joy is not None else 0.0)
                if self.gestures.capture_active:
                    continue
                # Speed normalized to ~60 Hz; right stick vertical scroll with accumulation.
                x, y = self._stick(key, "LEFT", axis(0), axis(1), p.deadzone)
                if x or y:
                    # Magnetism is always on in automatic mode, otherwise while ZR is held.
                    magnet_on = p.magnet_auto or self.gestures.is_pressed(key, MAGNET_TRIGGER)
                    event = self.output.move(x * p.mouse_speed * dt * 60, y * p.mouse_speed * dt * 60,
                                         p.magnet_strength if magnet_on else 0, dt,
                                         p.mouse_speed * 60, p.magnet_background)
                    if event and p.magnet_haptics:
                        self._rumble(key, event)
                _, scroll_y = self._stick(key, "RIGHT", axis(2), axis(3), p.deadzone)
                wheel = scroll_y * p.scroll_speed * dt * 10
                acc = self.scroll_acc.get(key, 0) - wheel
                steps = int(acc)
                if steps:
                    self.output.scroll(steps)
                    acc -= steps
                self.scroll_acc[key] = acc
        except pygame.error as exc:
            self.error.emit(str(exc))
            self.refresh()
