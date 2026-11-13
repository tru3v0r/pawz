"""Magnetic targets read from Windows: resize borders, caption buttons, desktop icons.

Each window is asked where it can be resized and where its caption buttons are by
hit-testing its frame (``WM_NCHITTEST``), the way Windows itself decides the cursor
shape. That gives the exact resize line (inside the invisible border on Windows 10
and 11), no edge at all for fixed-size or maximized windows, and the real buttons
of custom title bars (browsers, Electron...). A window that does not answer
(elevated, hung) falls back to its style and DWM frame bounds.

Probing a window takes tens of milliseconds, so it runs on a worker thread: the
input thread never waits, and uses the style-based guess until the probe is done.
The result is cached per window, relative to its rectangle, so moving or resizing
a window does not probe it again; it is refreshed in the background now and then.

The layout logic (``probe_layout``, ``fallback_layout``, ``targets_for``) is pure and
takes the hit test as a callable, so it is testable anywhere.
"""
from __future__ import annotations

import ctypes
import os
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from ctypes import wintypes
from dataclasses import dataclass

from pawz import APP_ID
from pawz.engine.magnet import PULL_RADIUS, Target

HTLEFT, HTRIGHT, HTTOP, HTBOTTOM = 10, 11, 12, 15
HTMINBUTTON, HTMAXBUTTON, HTCLOSE, HTHELP = 8, 9, 20, 21
BUTTON_CODES = frozenset({HTMINBUTTON, HTMAXBUTTON, HTCLOSE, HTHELP})
EDGE_SCAN = range(-3, 17)  # px around the outer rectangle edge, outside to inside
BUTTON_SCAN_X = (16, 30)  # px from the right edge where the close button is looked for
BUTTON_SCAN_HEIGHT = 80
BUTTON_ROW_WIDTH = 320
WS_THICKFRAME, WS_MINIMIZEBOX, WS_MAXIMIZEBOX, WS_SYSMENU = 0x40000, 0x20000, 0x10000, 0x80000
WS_CAPTION = 0xC00000
DESKTOP_CLASSES = frozenset({"Progman", "WorkerW"})
LAYOUT_TTL = 10.0
WINDOW_LIST_TTL = 0.25

HitTest = Callable[[int, int], "int | None"]
Rect = tuple[int, int, int, int]


@dataclass(frozen=True)
class FrameLayout:
    """Resize lines and caption buttons of a window, relative to its rectangle.

    ``edges`` maps a side to the inward distance of its resize line from the
    outer rectangle edge; ``buttons`` are centres as (distance left of the right
    edge, distance below the top edge).
    """
    edges: dict[str, float]
    buttons: tuple[tuple[float, float], ...] = ()


class _NoAnswer(Exception):
    """The window does not answer hit tests."""


def _ask(hit_test: HitTest, x: int, y: int) -> int:
    code = hit_test(x, y)
    if code is None:
        raise _NoAnswer
    return code


def _middle(values: list[int]) -> float | None:
    return (min(values) + max(values)) / 2 if values else None


def probe_layout(rect: Rect, hit_test: HitTest, zoomed: bool) -> FrameLayout | None:
    """Layout found by hit-testing, or None if the window does not answer."""
    left, top, right, bottom = rect
    mid_x, mid_y = (left + right) // 2, (top + bottom) // 2
    try:
        edges = {}
        if not zoomed:  # a maximized window has no resize border
            for side, code, point in (
                    ("left", HTLEFT, lambda o: (left + o, mid_y)),
                    ("right", HTRIGHT, lambda o: (right - 1 - o, mid_y)),
                    ("top", HTTOP, lambda o: (mid_x, top + o)),
                    ("bottom", HTBOTTOM, lambda o: (mid_x, bottom - 1 - o))):
                inset = _middle([o for o in EDGE_SCAN if _ask(hit_test, *point(o)) == code])
                if inset is not None:
                    edges[side] = inset
        return FrameLayout(edges, _probe_buttons(rect, hit_test))
    except _NoAnswer:
        return None


def _probe_buttons(rect: Rect, hit_test: HitTest) -> tuple[tuple[float, float], ...]:
    left, top, right, _bottom = rect
    row_y = None
    for from_right in BUTTON_SCAN_X:
        x = right - 1 - from_right
        hits = [y for y in range(top, top + BUTTON_SCAN_HEIGHT, 2)
                if _ask(hit_test, x, y) in BUTTON_CODES]
        if hits:
            # Refine the vertical extent to the pixel around the coarse hits.
            column = range(max(top, hits[0] - 2), hits[-1] + 3)
            row_y = _middle([y for y in column if _ask(hit_test, x, y) in BUTTON_CODES])
            break
    if row_y is None:
        return ()
    y = round(row_y)
    runs: list[list[int]] = []  # [code, rightmost x, leftmost x], scanned right to left
    misses = 0
    for x in range(right - 1, max(left, right - BUTTON_ROW_WIDTH), -2):
        code = _ask(hit_test, x, y)
        if code in BUTTON_CODES:
            misses = 0
            if runs and runs[-1][0] == code and runs[-1][2] - x <= 4:
                runs[-1][2] = x
            else:
                runs.append([code, x, x])
        elif runs:
            misses += 1
            if misses > 20:  # 40 px past the last button: end of the row
                break
    return tuple((right - (start + end) / 2, row_y - top) for _code, start, end in runs)


def fallback_layout(rect: Rect, frame: Rect | None, style: int, zoomed: bool,
                    caption: Rect | None) -> FrameLayout:
    """Best guess for a window that does not answer hit tests.

    ``frame`` is the visible frame (DWM extended frame bounds) and ``caption`` the
    caption buttons' bounds relative to the window, both when available.
    """
    left, top, right, bottom = rect
    edges = {}
    if style & WS_THICKFRAME and not zoomed:
        # The resize band runs from the outer (invisible) border to the visible one.
        f_left, f_top, f_right, f_bottom = frame or rect
        edges = {"left": max(2.0, (f_left - left) / 2), "top": max(2.0, (f_top - top) / 2),
                 "right": max(2.0, (right - f_right) / 2),
                 "bottom": max(2.0, (bottom - f_bottom) / 2)}
    buttons: tuple[tuple[float, float], ...] = ()
    count = (bool(style & WS_SYSMENU) + bool(style & WS_MINIMIZEBOX)
             + bool(style & WS_MAXIMIZEBOX))
    if caption and style & WS_CAPTION == WS_CAPTION and count:
        c_left, c_top, c_right, c_bottom = caption
        width = (c_right - c_left) / count
        if width < 16 or c_bottom - c_top < 12:
            return FrameLayout(edges)  # bounds of a custom-drawn title bar: meaningless
        y = (c_top + c_bottom) / 2
        buttons = tuple((right - left - c_right + width * (i + .5), y) for i in range(count))
    return FrameLayout(edges, buttons)


def targets_for(rect: Rect, layout: FrameLayout, cursor: tuple[int, int],
                group: str) -> list[Target]:
    """Targets of a window: its resize lines (as the cursor's projection onto
    each) and its caption buttons."""
    left, top, right, bottom = rect
    x, y = cursor
    targets = []
    edges = layout.edges
    if "top" in edges or "bottom" in edges:
        along_x = min(max(x, left), right)
        for side, line_y in (("top", top + edges.get("top", 0)),
                             ("bottom", bottom - 1 - edges.get("bottom", 0))):
            if side in edges:
                targets.append(Target(along_x, line_y, "hline", left, right))
    if "left" in edges or "right" in edges:
        along_y = min(max(y, top), bottom)
        for side, line_x in (("left", left + edges.get("left", 0)),
                             ("right", right - 1 - edges.get("right", 0))):
            if side in edges:
                targets.append(Target(line_x, along_y, "vline", top, bottom))
    targets.extend(Target(right - from_right, top + below, group=group)
                   for from_right, below in layout.buttons)
    return targets


# --------------------------------------------------------------------------- Windows

if os.name == "nt":
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _dwmapi = ctypes.WinDLL("dwmapi")
    _user32.SendMessageTimeoutW.argtypes = (
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM, wintypes.UINT,
        wintypes.UINT, ctypes.POINTER(ctypes.c_ssize_t))
    _user32.SendMessageTimeoutW.restype = ctypes.c_ssize_t
    _user32.GetForegroundWindow.restype = wintypes.HWND
    _user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    _user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
    _user32.GetWindowLongW.restype = ctypes.c_long
    _user32.IsZoomed.argtypes = (wintypes.HWND,)
    _user32.IsIconic.argtypes = (wintypes.HWND,)
    _user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    _user32.GetDpiForWindow.argtypes = (wintypes.HWND,)
    _user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    _user32.WindowFromPoint.argtypes = (wintypes.POINT,)
    _user32.WindowFromPoint.restype = wintypes.HWND
    _user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
    _user32.GetAncestor.restype = wintypes.HWND
    _dwmapi.DwmGetWindowAttribute.argtypes = (
        wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD)
    _ENUM_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    _user32.EnumWindows.argtypes = (_ENUM_PROC, wintypes.LPARAM)

WM_NCHITTEST = 0x0084
SMTO_ABORTIFHUNG, SMTO_ERRORONEXIT = 0x0002, 0x0020
HIT_TEST_TIMEOUT_MS = 15
DWMWA_EXTENDED_FRAME_BOUNDS, DWMWA_CAPTION_BUTTON_BOUNDS, DWMWA_CLOAKED = 9, 5, 14
GWL_STYLE = -16
GA_ROOT = 2

_layouts: dict[int, tuple[tuple, float, FrameLayout]] = {}
_probing: set[int] = set()
_prober = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"{APP_ID}-window-probe")
_window_list: tuple[float, list[int]] = (-1.0, [])
_icons: list[tuple[int, int]] = []
_icons_read_at = -1.0
ICONS_TTL = 1.0


def _hit_tester(hwnd: int) -> HitTest:
    def hit_test(x: int, y: int) -> int | None:
        result = ctypes.c_ssize_t()
        lparam = (x & 0xFFFF) | ((y & 0xFFFF) << 16)
        if not _user32.SendMessageTimeoutW(hwnd, WM_NCHITTEST, 0, lparam,
                                           SMTO_ABORTIFHUNG | SMTO_ERRORONEXIT,
                                           HIT_TEST_TIMEOUT_MS, ctypes.byref(result)):
            return None
        return ctypes.c_short(result.value & 0xFFFF).value  # HTERROR/HTTRANSPARENT are negative
    return hit_test


def _rect(hwnd: int) -> Rect | None:
    rect = wintypes.RECT()
    if not _user32.GetWindowRect(hwnd, ctypes.byref(rect)) or rect.right <= rect.left:
        return None
    return rect.left, rect.top, rect.right, rect.bottom


def _dwm_rect(hwnd: int, attribute: int) -> Rect | None:
    rect = wintypes.RECT()
    if _dwmapi.DwmGetWindowAttribute(hwnd, attribute, ctypes.byref(rect), ctypes.sizeof(rect)):
        return None
    return rect.left, rect.top, rect.right, rect.bottom


def _class_name(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(64)
    _user32.GetClassNameW(hwnd, buffer, 64)
    return buffer.value


def _layout(hwnd: int, rect: Rect) -> FrameLayout:
    """Cached layout of a window; probing (again) happens on the worker thread."""
    style = _user32.GetWindowLongW(hwnd, GWL_STYLE) & 0xFFFFFFFF
    zoomed = bool(_user32.IsZoomed(hwnd))
    key = (style, zoomed, _user32.GetDpiForWindow(hwnd))
    cached = _layouts.get(hwnd)
    layout = cached[2] if cached is not None and cached[0] == key else None
    recent = cached is not None and time.monotonic() - cached[1] < LAYOUT_TTL
    if not (layout and recent) and hwnd not in _probing:
        _probing.add(hwnd)
        _prober.submit(_probe, hwnd, rect, key, style, zoomed)
    # Not probed yet: no targets for the few milliseconds the probe takes.
    return layout or FrameLayout({})


def _fallback(hwnd: int, rect: Rect, style: int, zoomed: bool) -> FrameLayout:
    return fallback_layout(rect, _dwm_rect(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS), style, zoomed,
                           _dwm_rect(hwnd, DWMWA_CAPTION_BUTTON_BOUNDS))


def _probe(hwnd: int, rect: Rect, key: tuple, style: int, zoomed: bool) -> None:
    try:
        layout = probe_layout(rect, _hit_tester(hwnd), zoomed)
        if layout is None:
            layout = _fallback(hwnd, rect, style, zoomed)
        if len(_layouts) > 256:
            _layouts.clear()
        _layouts[hwnd] = (key, time.monotonic(), layout)
    except OSError:
        pass
    finally:
        _probing.discard(hwnd)


def _visible_windows() -> list[int]:
    """Visible, non-minimized, non-cloaked top-level windows, front to back."""
    global _window_list
    now = time.monotonic()
    if now - _window_list[0] < WINDOW_LIST_TTL:
        return _window_list[1]
    found = []

    def collect(hwnd, _):
        cloaked = wintypes.DWORD()
        if (_user32.IsWindowVisible(hwnd) and not _user32.IsIconic(hwnd)
                and not (not _dwmapi.DwmGetWindowAttribute(
                    hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
                    and cloaked.value)):
            found.append(hwnd)
        return True

    _user32.EnumWindows(_ENUM_PROC(collect), 0)
    _window_list = (now, found)
    return found


def _desktop_icons(read: Callable[[], list[tuple[int, int]]]) -> list[tuple[int, int]]:
    """Icon centres, read on the worker thread (it reads another process's memory)."""
    global _icons_read_at
    now = time.monotonic()
    if now - _icons_read_at >= ICONS_TTL:
        _icons_read_at = now

        def refresh():
            global _icons
            try:
                _icons = read()
            except OSError:
                pass

        _prober.submit(refresh)
    return _icons


def _root_at(point: tuple[float, float]) -> int:
    hwnd = _user32.WindowFromPoint(wintypes.POINT(round(point[0]), round(point[1])))
    return _user32.GetAncestor(hwnd, GA_ROOT) if hwnd else 0


def _near(rect: Rect, cursor: tuple[int, int]) -> bool:
    left, top, right, bottom = rect
    x, y = cursor
    return (left - PULL_RADIUS <= x <= right + PULL_RADIUS
            and top - PULL_RADIUS <= y <= bottom + PULL_RADIUS)


def interaction_targets(cursor: tuple[int, int], background: bool,
                        desktop_icons: Callable[[], list[tuple[int, int]]]) -> list[Target]:
    """Targets around the cursor: those of the foreground window, or with
    ``background`` those of every visible window, where they are not covered."""
    foreground = _user32.GetForegroundWindow()
    windows = _visible_windows() if background else [foreground] if foreground else []
    targets: list[Target] = []
    desktop_shown = False
    for hwnd in windows:
        if _class_name(hwnd) in DESKTOP_CLASSES:
            desktop_shown = desktop_shown or background or hwnd == foreground
            continue
        rect = _rect(hwnd)
        if rect is None or not _near(rect, cursor):
            continue
        found = targets_for(rect, _layout(hwnd, rect), cursor, f"caption:{hwnd}")
        if background:
            found = [t for t in found if _root_at((t.x, t.y)) == hwnd]
        targets.extend(found)
    if desktop_shown:
        icons = (Target(*center) for center in _desktop_icons(desktop_icons))
        targets.extend(t for t in icons
                       if not background or _class_name(_root_at((t.x, t.y))) in DESKTOP_CLASSES)
    return targets
