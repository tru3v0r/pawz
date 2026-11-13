"""Magnetic targets of a window, from its hit-test answers (pure: no Windows calls)."""
import pytest

from pawz.infra.window_targets import (
    HTBOTTOM,
    HTCLOSE,
    HTLEFT,
    HTMAXBUTTON,
    HTMINBUTTON,
    HTRIGHT,
    HTTOP,
    WS_CAPTION,
    WS_MAXIMIZEBOX,
    WS_MINIMIZEBOX,
    WS_SYSMENU,
    WS_THICKFRAME,
    FrameLayout,
    fallback_layout,
    probe_layout,
    targets_for,
)

RECT = (100, 50, 900, 650)
HTCLIENT = 1


def windows10_window(resizable=True):
    """Hit test of a Windows 10 style window: 7 px invisible border + 3 px of
    visible frame on the sides and bottom, 4 px at the top, three 46 px caption
    buttons on a 30 px high row."""
    left, top, right, bottom = RECT

    def hit(x, y):
        if not (left <= x < right and top <= y < bottom):
            return 0
        if top + 1 <= y < top + 31:
            for index, code in enumerate((HTCLOSE, HTMAXBUTTON, HTMINBUTTON)):
                edge = right - 7 - 46 * index
                if edge - 46 <= x < edge:
                    return code
        if not resizable:
            return HTCLIENT
        if x < left + 10:
            return HTLEFT
        if x >= right - 10:
            return HTRIGHT
        if y < top + 4:
            return HTTOP
        if y >= bottom - 10:
            return HTBOTTOM
        return HTCLIENT
    return hit


def test_resize_lines_sit_in_the_middle_of_the_resize_band():
    layout = probe_layout(RECT, windows10_window(), zoomed=False)
    assert layout is not None
    assert layout.edges == {"left": 4.5, "right": 4.5, "top": 1.5, "bottom": 4.5}
    targets = targets_for(RECT, layout, (300, 200), "w")
    lines = {(t.kind, t.x if t.kind == "vline" else t.y) for t in targets if t.kind != "point"}
    assert lines == {("vline", 104.5), ("vline", 894.5), ("hline", 51.5), ("hline", 644.5)}
    edge = next(t for t in targets if t.kind == "vline")
    assert edge.y == 200  # the cursor's projection onto the edge


def test_caption_buttons_are_found_and_centred():
    layout = probe_layout(RECT, windows10_window(), zoomed=False)
    assert layout is not None
    buttons = [t for t in targets_for(RECT, layout, (300, 200), "w") if t.kind == "point"]
    expected = [(869.5, 65.5), (823.5, 65.5), (777.5, 65.5)]  # close, maximize, minimize
    assert len(buttons) == 3
    for button, (x, y) in zip(buttons, expected, strict=True):
        assert button.x == pytest.approx(x, abs=1) and button.y == pytest.approx(y, abs=1)
        assert button.group == "w"


def test_fixed_size_and_maximized_windows_have_no_magnetic_edges():
    fixed = probe_layout(RECT, windows10_window(resizable=False), zoomed=False)
    maximized = probe_layout(RECT, windows10_window(), zoomed=True)
    for layout in (fixed, maximized):
        assert layout is not None and layout.edges == {}
        assert len(layout.buttons) == 3


def test_a_window_that_does_not_answer_is_not_probed():
    assert probe_layout(RECT, lambda _x, _y: None, zoomed=False) is None


def test_fallback_uses_style_and_dwm_bounds():
    style = WS_THICKFRAME | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX
    rect = (0, 0, 800, 600)
    layout = fallback_layout(rect, (7, 0, 793, 593), style, False, (655, 1, 793, 31))
    assert layout.edges == {"left": 3.5, "top": 2.0, "right": 3.5, "bottom": 3.5}
    assert [round(x) for x, _y in layout.buttons] == [30, 76, 122]
    assert fallback_layout(rect, None, WS_CAPTION | WS_SYSMENU, False, None) == FrameLayout({})
