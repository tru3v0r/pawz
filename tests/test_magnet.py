"""Rules of the sticky magnet (pure: no Windows calls)."""
import pytest

from pawz.engine.magnet import (
    IDLE_RESET,
    SNAP_RADIUS,
    Magnet,
    MagnetStep,
    Target,
    escape_threshold,
)

FULL_SPEED = 50.0  # small, so thresholds stay a few dozen pixels in these tests

POINT = Target(100, 0)


def captured_magnet(strength=100):
    magnet = Magnet()
    step = magnet.step((92, 0), 5, 0, strength, [POINT], now=0,
                       full_speed=FULL_SPEED)  # within any snap radius
    assert step == MagnetStep(warp=(100, 0), event="captured")
    return magnet


def test_target_ahead_within_snap_radius_captures():
    captured_magnet()


def test_target_behind_never_captures():
    magnet = Magnet()
    step = magnet.step((110, 0), 5, 0, 100, [POINT], now=0)
    assert step.event is None and step.warp is None and magnet.captured is None


@pytest.mark.parametrize("strength", [25, 50, 100])
def test_hold_absorbs_movement_until_the_escape_threshold(strength):
    magnet = captured_magnet(strength)
    threshold = escape_threshold(strength / 100, FULL_SPEED)
    pushed, now = 0.0, 0.0
    while True:
        now += 0.004
        step = magnet.step((100, 0), 0, 1, strength, [POINT], now=now, full_speed=FULL_SPEED)
        pushed += 1
        if step.event == "released":
            break
        assert step.delta == (0.0, 0.0)
    assert threshold < pushed <= threshold + 1
    # Placed just outside the capture zone, not carried by the whole effort.
    assert step.warp == (100, round(SNAP_RADIUS * strength / 100 + 3))
    assert step.delta == (0.0, 0.0)


def test_released_target_does_not_recapture_until_left_behind():
    magnet = captured_magnet()
    for i in range(30):
        magnet.step((100, 0), -1, 0, 100, [POINT], now=0.004 * i, full_speed=FULL_SPEED)
    assert magnet.captured is None
    # Still close: coming back does not recapture yet.
    assert magnet.step((95, 0), 1, 0, 100, [POINT], now=0.2).event is None
    # Far enough away, the target is armed again.
    magnet.step((50, 0), -1, 0, 100, [POINT], now=0.21)
    assert magnet.step((70, 0), 5, 0, 100, [POINT], now=0.22).event == "captured"


def test_escape_effort_is_forgotten_after_a_pause():
    magnet = captured_magnet()
    magnet.step((100, 0), 0, 15, 100, [POINT], now=0.01)
    assert magnet.step((100, 0), 0, 15, 100, [POINT], now=0.01 + IDLE_RESET + 0.01).event is None


def test_edge_hold_lets_the_cursor_glide_along_it():
    edge = Target(40, 0, "hline", 0, 500)
    magnet = Magnet()
    assert magnet.step((40, 20), 0, -5, 100, [edge], now=0).event == "captured"
    step = magnet.step((40, 0), 3, 0.5, 100, [Target(40, 0, "hline", 0, 500)], now=0.004)
    assert step.delta == (3, 0.0)  # along the edge: free; across: absorbed


def test_vanished_target_releases_silently():
    magnet = captured_magnet()
    step = magnet.step((100, 0), 1, 0, 100, [], now=0.004)
    assert step == MagnetStep((1, 0))
    assert magnet.captured is None


def test_cursor_moved_elsewhere_releases_silently():
    magnet = captured_magnet()
    step = magnet.step((300, 300), 1, 0, 100, [POINT], now=0.004)
    assert step.event is None and magnet.captured is None


def test_zero_strength_disables_and_resets():
    magnet = captured_magnet()
    assert magnet.step((100, 0), 1, 2, 0, [POINT], now=0.004) == MagnetStep((1, 2))
    assert magnet.captured is None


def test_pull_bends_toward_targets_ahead_only():
    magnet = Magnet()
    ahead = magnet.step((0, 0), 1, 0, 100, [Target(100, 30)], now=0)
    assert ahead.delta[1] > 0
    behind = magnet.step((0, 0), -1, 0, 100, [Target(100, 30)], now=0.004)
    assert behind.delta == (-1, 0)


@pytest.mark.parametrize(("strength", "seconds"), [(25, 0.145), (50, 0.23), (100, 0.40)])
def test_escape_effort_is_a_push_duration_independent_of_pointer_speed(strength, seconds):
    for speed in (8 * 60, 16 * 60, 40 * 60):
        assert escape_threshold(strength / 100, speed) / speed == pytest.approx(seconds)


def test_release_from_an_edge_only_steps_off_it_perpendicularly():
    magnet = Magnet()
    edge = Target(40, 0, "hline", 0, 500)
    magnet.step((40, 20), 0, -5, 50, [edge], now=0, full_speed=FULL_SPEED)
    step = None
    for i in range(200):
        step = magnet.step((40, 0), 1, 1, 50, [Target(40, 0, "hline", 0, 500)],
                           now=0.004 * (i + 1), full_speed=FULL_SPEED)
        if step.event == "released":
            break
    assert step is not None and step.event == "released"
    assert step.warp == (41, 23)  # glide kept, 20 px capture radius + 3 px clearance


ROW = [Target(100, 0, group="w"), Target(150, 0, group="w"), Target(200, 0, group="w")]


def captured_in_row():
    magnet = Magnet()
    assert magnet.step((92, 0), 5, 0, 50, ROW, now=0).event == "captured"
    return magnet


def test_sideways_push_navigates_straight_to_the_next_button_centred():
    magnet = captured_in_row()
    assert magnet.step((100, 0), 1, 0.2, 50, ROW, now=0.004) == MagnetStep(
        warp=(150, 0), event="captured")


def test_held_push_repeats_navigation_then_escapes_past_the_last_button():
    magnet = captured_in_row()
    magnet.step((100, 0), 1, 0, 50, ROW, now=0.004)
    assert magnet.step((150, 0), 1, 0, 50, ROW, now=0.1) == MagnetStep()  # waits
    assert magnet.step((150, 0), 1, 0, 50, ROW, now=0.31).warp == (200, 0)
    now, step = 0.31, MagnetStep()
    while step.event != "released":  # no button further right: a normal escape
        now += 0.004
        step = magnet.step((200, 0), 20, 0, 50, ROW, now=now)
    assert step.warp == (223, 0)


def test_a_new_flick_after_a_pause_navigates_at_once():
    magnet = captured_in_row()
    magnet.step((100, 0), 1, 0, 50, ROW, now=0.004)
    assert magnet.step((150, 0), -1, 0, 50, ROW, now=0.2).warp == (100, 0)


def test_vertical_push_on_a_button_escapes_instead_of_navigating():
    magnet = captured_in_row()
    step = magnet.step((100, 0), 0.5, 1, 50, ROW, now=0.004)
    assert step == MagnetStep() and magnet.captured == ROW[0]


BUTTONS = [Target(869, 65, group="w"), Target(823, 65, group="w"), Target(777, 65, group="w")]


def held_on(edge, start, dx, dy):
    magnet = Magnet()
    assert magnet.step(start, dx, dy, 50, [edge, *BUTTONS], now=0).event == "captured"
    assert magnet.captured == edge
    return magnet


def test_pushing_left_from_the_right_edge_near_the_top_navigates_to_the_rightmost_button():
    magnet = held_on(Target(894, 60, "vline", 50, 650), (880, 60), 5, 0)
    step = magnet.step((894, 60), -1, 0.2, 50, [Target(894, 60, "vline", 50, 650), *BUTTONS],
                       now=0.004)
    assert step == MagnetStep(warp=(869, 65), event="captured")


def test_pushing_down_from_the_top_edge_near_the_right_navigates_to_the_closest_button():
    magnet = held_on(Target(830, 52, "hline", 100, 900), (830, 60), 0, -5)
    step = magnet.step((830, 52), 0.2, 1, 50, [Target(830, 52, "hline", 100, 900), *BUTTONS],
                       now=0.004)
    assert step == MagnetStep(warp=(823, 65), event="captured")


def test_edges_far_from_the_buttons_keep_the_usual_escape():
    magnet = held_on(Target(894, 400, "vline", 50, 650), (880, 400), 5, 0)
    step = magnet.step((894, 400), -1, 0, 50, [Target(894, 400, "vline", 50, 650), *BUTTONS],
                       now=0.004)
    assert step == MagnetStep() and magnet.captured is not None
    magnet = held_on(Target(300, 52, "hline", 100, 900), (300, 60), 0, -5)
    step = magnet.step((300, 52), 0, 1, 50, [Target(300, 52, "hline", 100, 900), *BUTTONS],
                       now=0.004)
    assert step == MagnetStep() and magnet.captured is not None
