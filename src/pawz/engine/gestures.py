"""Per-device gesture state machine: press, release, hold, chords and capture.

The engine never performs side effects. Each call returns a list of effects that
the caller (ControllerManager) executes against the operating system or the UI.
This keeps the rules testable as plain tables of inputs and expected effects.

Rules
- A button that belongs to no chord acts on release, except a ``*_click`` action,
  which holds the mouse button from press to release.
- A button that belongs to at least one chord is deferred: when every button of
  a chord is held, the chord fires once (a ``*_click`` chord holds the mouse
  button until any of its buttons is released) and its buttons are consumed.
  A deferred button that was not consumed acts alone on release.
- Layers: a chord that includes a layer button (``LAYER_BUTTONS``, ZL) is a layer
  binding. It fires only when the layer button is already held as the other
  button goes down, and it never defers that other button: without ZL held, A
  still holds its click at once. The layer button itself is deferred and, when
  used as a modifier, consumed.
- A long press (``LONG_PRESS_BUTTONS``) fires once after ``LONG_PRESS_DELAY`` and
  suppresses the action on release.
- While capture is active, presses and releases are reported instead of acted on;
  buttons already held when capture starts never act on release.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from pawz.engine.actions import mouse_button

LONG_PRESS_BUTTONS = frozenset({"GUIDE"})
LAYER_BUTTONS = frozenset({"LEFT_TRIGGER"})
LONG_PRESS_DELAY = 0.8


@dataclass(frozen=True)
class Dispatch:
    """Perform the binding currently resolved for ``trigger``."""
    device: str
    trigger: str


@dataclass(frozen=True)
class MouseDown:
    device: str
    button: str  # "left" | "right" | "middle"


@dataclass(frozen=True)
class MouseUp:
    device: str
    button: str


@dataclass(frozen=True)
class CaptureInput:
    device: str
    button: str
    pressed: bool


@dataclass(frozen=True)
class LongPress:
    device: str
    button: str


Effect = Dispatch | MouseDown | MouseUp | CaptureInput | LongPress


def _buttons(trigger: str) -> list[str]:
    return trigger.split("+")




@dataclass
class DeviceGestures:
    """Gesture state of one controller."""
    pressed: dict[str, float] = field(default_factory=dict)
    long_handled: set[str] = field(default_factory=set)
    held_clicks: dict[str, str] = field(default_factory=dict)
    captured: set[str] = field(default_factory=set)
    deferred: set[str] = field(default_factory=set)
    consumed: set[str] = field(default_factory=set)
    combo_clicks: dict[str, str] = field(default_factory=dict)
    fired_combos: set[str] = field(default_factory=set)

    def forget(self, button: str) -> None:
        self.pressed.pop(button, None)
        self.long_handled.discard(button)
        self.deferred.discard(button)
        self.consumed.discard(button)


class GestureEngine:
    def __init__(self) -> None:
        self.devices: dict[str, DeviceGestures] = {}
        self.capture_active = False

    def device(self, device: str) -> DeviceGestures:
        return self.devices.setdefault(device, DeviceGestures())

    def is_pressed(self, device: str, button: str) -> bool:
        state = self.devices.get(device)
        return state is not None and button in state.pressed

    # -- inputs ---------------------------------------------------------------

    def press(self, device: str, button: str, now: float,
              actions: Mapping[str, str]) -> list[Effect]:
        """Button went down. ``actions`` maps each normalized trigger of the
        current context (single buttons and chords) to its action name."""
        state = self.device(device)
        state.pressed[button] = now
        if self.capture_active:
            state.captured.add(button)
            return [CaptureInput(device, button, True)]
        chords = {trigger: action for trigger, action in actions.items() if "+" in trigger}
        layered = {trigger: action for trigger, action in chords.items()
                   if LAYER_BUTTONS & set(_buttons(trigger))}
        plain = {trigger: action for trigger, action in chords.items() if trigger not in layered}
        if button not in LAYER_BUTTONS:
            for trigger, action in layered.items():
                if button in _buttons(trigger) and set(_buttons(trigger)) <= state.pressed.keys():
                    state.deferred.add(button)
                    return self._start_chord(device, state, trigger, action)
        in_layer = button in LAYER_BUTTONS and any(button in _buttons(t) for t in layered)
        if in_layer or any(button in _buttons(trigger) for trigger in plain):
            state.deferred.add(button)
            effects: list[Effect] = []
            for trigger, action in plain.items():
                if set(_buttons(trigger)) <= state.pressed.keys():
                    effects += self._start_chord(device, state, trigger, action)
            return effects
        mouse = mouse_button(actions.get(button, "none"))
        if mouse is None:
            return []
        state.held_clicks[button] = mouse
        return [MouseDown(device, mouse)]

    def release(self, device: str, button: str) -> list[Effect]:
        state = self.device(device)
        effects = self._stop_chord_clicks(device, state, button)
        if button in state.captured:
            state.captured.discard(button)
            if self.capture_active:
                effects.append(CaptureInput(device, button, False))
        elif button in state.deferred:
            if button not in state.consumed:
                effects.append(Dispatch(device, button))
        elif button in state.held_clicks:
            effects.append(MouseUp(device, state.held_clicks.pop(button)))
        elif button not in state.long_handled:
            effects.append(Dispatch(device, button))
        state.forget(button)
        return effects

    def tick(self, device: str, now: float) -> list[Effect]:
        """Time passed with the current buttons still held."""
        state = self.devices.get(device)
        if state is None:
            return []
        effects: list[Effect] = []
        for button, since in state.pressed.items():
            if (button in LONG_PRESS_BUTTONS and button not in state.long_handled
                    and button not in state.deferred and button not in state.captured
                    and now - since >= LONG_PRESS_DELAY):
                state.long_handled.add(button)
                effects.append(LongPress(device, button))
        return effects

    # -- lifecycle --------------------------------------------------------------

    def begin_capture(self) -> list[Effect]:
        """Release every held mouse button; held controller buttons stay inert."""
        self.capture_active = True
        effects: list[Effect] = []
        for device, state in self.devices.items():
            effects += [MouseUp(device, mouse) for mouse in state.held_clicks.values()]
            state.held_clicks.clear()
            effects += [MouseUp(device, mouse) for mouse in state.combo_clicks.values()]
            state.combo_clicks.clear()
            state.fired_combos.clear()
            state.captured.update(state.pressed)
        return effects

    def end_capture(self) -> None:
        self.capture_active = False

    def release_clicks(self) -> list[Effect]:
        """Let go of every held mouse button; buttons still held become inert
        (no action when they are released)."""
        effects: list[Effect] = []
        for device, state in self.devices.items():
            effects += [MouseUp(device, mouse) for mouse in state.held_clicks.values()]
            effects += [MouseUp(device, mouse) for mouse in state.combo_clicks.values()]
            state.held_clicks.clear()
            state.combo_clicks.clear()
            state.fired_combos.clear()
            state.captured.update(state.pressed)
        return effects

    def remove_device(self, device: str) -> list[Effect]:
        """Device disconnected: release everything it was holding."""
        state = self.devices.pop(device, None)
        if state is None:
            return []
        effects: list[Effect] = [MouseUp(device, mouse) for mouse in state.combo_clicks.values()]
        effects += [MouseUp(device, mouse) for mouse in state.held_clicks.values()]
        if self.capture_active:
            effects += [CaptureInput(device, button, False)
                        for button in state.pressed if button in state.captured]
        return effects

    # -- chords ---------------------------------------------------------------

    def _start_chord(self, device: str, state: DeviceGestures,
                     trigger: str, action: str) -> list[Effect]:
        if trigger in state.fired_combos:
            return []
        state.fired_combos.add(trigger)
        state.consumed.update(_buttons(trigger))
        mouse = mouse_button(action)
        if mouse is None:
            return [Dispatch(device, trigger)]
        state.combo_clicks[trigger] = mouse
        return [MouseDown(device, mouse)]

    @staticmethod
    def _stop_chord_clicks(device: str, state: DeviceGestures, button: str) -> list[Effect]:
        effects: list[Effect] = []
        for trigger in [t for t in state.combo_clicks if button in _buttons(t)]:
            effects.append(MouseUp(device, state.combo_clicks.pop(trigger)))
        state.fired_combos = {t for t in state.fired_combos if button not in _buttons(t)}
        return effects
