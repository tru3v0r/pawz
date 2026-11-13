from pawz.core.controller_inputs import (
    SDL2_AXIS_TO_LOGICAL,
    LogicalAxis,
    LogicalButton,
    logical_button_for_sdl2,
    migrate_legacy_trigger,
)


def test_sdl2_standard_buttons_are_explicitly_adapted_to_logical_names():
    assert logical_button_for_sdl2(0) == "SOUTH"
    assert logical_button_for_sdl2(1) == "EAST"
    assert logical_button_for_sdl2(2) == "WEST"
    assert logical_button_for_sdl2(3) == "NORTH"
    assert logical_button_for_sdl2(9) == "LEFT_SHOULDER"
    assert logical_button_for_sdl2(10) == "RIGHT_SHOULDER"
    assert logical_button_for_sdl2(11) == "DPAD_UP"
    assert logical_button_for_sdl2(14) == "DPAD_RIGHT"
    assert logical_button_for_sdl2(99) is None


def test_sdl2_triggers_remain_analog_axes():
    assert SDL2_AXIS_TO_LOGICAL[4] is LogicalAxis.LEFT_TRIGGER
    assert SDL2_AXIS_TO_LOGICAL[5] is LogicalAxis.RIGHT_TRIGGER
    assert LogicalButton.LEFT_SHOULDER.value != LogicalAxis.LEFT_TRIGGER.value


def test_legacy_profile_chords_migrate_without_changing_button_order():
    assert migrate_legacy_trigger("a+b") == "SOUTH+EAST"
    assert migrate_legacy_trigger("l+right_stick") == "LEFT_SHOULDER+RIGHT_STICK"
    assert migrate_legacy_trigger("SOUTH+DPAD_UP") == "SOUTH+DPAD_UP"
