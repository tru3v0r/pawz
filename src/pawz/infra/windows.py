"""Windows-only input injection and interaction-target detection."""
import ctypes
import json
import math
import os
import time
from ctypes import wintypes
from pathlib import Path

import psutil

from pawz import APP_ID, env
from pawz.core.pointer import SubpixelAccumulator
from pawz.engine import actions
from pawz.engine.magnet import Magnet, Target
from pawz.infra import window_targets

user32 = ctypes.windll.user32 if os.name == "nt" else None
VK = {"ctrl": 0x11, "shift": 0x10, "alt": 0x12, "tab": 0x09, "win": 0x5B,
      "left": 0x25, "right": 0x27, "up": 0x26, "down": 0x28, "enter": 0x0D,
      "esc": 0x1B, "space": 0x20, "backspace": 0x08, "insert": 0x2D, "delete": 0x2E,
      "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
      "printscreen": 0x2C, "menu": 0x5D, "capslock": 0x14,
      "plus": 0xBB, "minus": 0xBD, "comma": 0xBC, "period": 0xBE,
      "volume_up": 0xAF, "volume_down": 0xAE, "volume_mute": 0xAD,
      "media_play_pause": 0xB3, "media_next": 0xB0, "media_previous": 0xB1,
      "media_stop": 0xB2, "browser_back": 0xA6, "browser_forward": 0xA7,
      "browser_refresh": 0xA8, "browser_home": 0xAC}
VK.update({f"f{number}": 0x6F + number for number in range(1, 25)})
# Without KEYEVENTF_EXTENDEDKEY these are delivered as their numeric keypad twins.
EXTENDED_KEYS = frozenset({0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28,
                           0x2D, 0x2E, 0x5B, 0x5D})
KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP = 0x0001, 0x0002
MOUSEEVENTF_MOVE, MOUSEEVENTF_WHEEL = 0x0001, 0x0800
INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
# Tag carried in dwExtraInfo so hooks can recognize our injected input: the
# application id's first four letters ("PAWZ" = 0x5041575A).
INPUT_TAG = int.from_bytes(APP_ID.upper().encode("ascii")[:4].ljust(4, b"_"), "big")
MOUSE_FLAGS = {"left": (0x0002, 0x0004), "right": (0x0008, 0x0010),
               "middle": (0x0020, 0x0040)}
_desktop_icon_cache: tuple[float, list[tuple[int, int]]] = (0.0, [])
_pointer_residual = SubpixelAccumulator()
_magnet = Magnet()
_last_process: tuple[int, str] = (0, "")
_native_send_input = None


def key_code(token: str) -> int:
    code = VK.get(token)
    if code is None and len(token) == 1 and token.isascii() and token.isalnum():
        code = ord(token.upper())
    if code is None:
        raise ValueError(f"Unknown key: {token}")
    return code


class _MouseInput(ctypes.Structure):
    _fields_ = (("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.LONG),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t))


class _KeyboardInput(ctypes.Structure):
    _fields_ = (("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t))


class _HardwareInput(ctypes.Structure):
    _fields_ = (("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD))


class _InputUnion(ctypes.Union):
    _fields_ = (("mi", _MouseInput), ("ki", _KeyboardInput), ("hi", _HardwareInput))


class _Input(ctypes.Structure):
    _fields_ = (("type", wintypes.DWORD), ("union", _InputUnion))


def _send_input(inputs: list[_Input]) -> None:
    """Inject a batch atomically: no other input can interleave inside it.

    UIPI silently drops input aimed at elevated windows; SendInput does not
    report it, so only genuine API failures raise here.
    """
    global _native_send_input
    if _native_send_input is None:
        _native_send_input = ctypes.WinDLL("user32", use_last_error=True).SendInput
        _native_send_input.argtypes = (wintypes.UINT, ctypes.POINTER(_Input), ctypes.c_int)
        _native_send_input.restype = wintypes.UINT
    array = (_Input * len(inputs))(*inputs)
    if _native_send_input(len(inputs), array, ctypes.sizeof(_Input)) != len(inputs):
        raise ctypes.WinError(ctypes.get_last_error())


def send_keys(events: list[tuple[int, int]]) -> None:
    """Send (virtual key, KEYEVENTF_* flags) events in one SendInput call."""
    inputs = []
    for code, flags in events:
        scan = user32.MapVirtualKeyW(code, 0) if user32 is not None else 0
        inputs.append(_Input(INPUT_KEYBOARD, _InputUnion(ki=_KeyboardInput(
            code, scan, flags, 0, INPUT_TAG))))
    _send_input(inputs)


def send_mouse(flags: int, dx: int = 0, dy: int = 0, data: int = 0) -> None:
    _send_input([_Input(INPUT_MOUSE, _InputUnion(mi=_MouseInput(
        dx, dy, data, flags, 0, INPUT_TAG)))])


def key_combo(keys: str) -> None:
    codes = [key_code(token) for token in keys.lower().replace(" ", "").split("+")]
    extended = [KEYEVENTF_EXTENDEDKEY if code in EXTENDED_KEYS else 0 for code in codes]
    presses = list(zip(codes, extended, strict=True))
    releases = [(code, flags | KEYEVENTF_KEYUP) for code, flags in reversed(presses)]
    send_keys(presses + releases)


def mouse_button_down(which: str) -> None:
    send_mouse(MOUSE_FLAGS[which][0])


def mouse_button_up(which: str) -> None:
    send_mouse(MOUSE_FLAGS[which][1])


def click(which: str) -> None:
    mouse_button_down(which)
    mouse_button_up(which)


def _find_desktop_list_view() -> int | None:
    find_window = user32.FindWindowW
    find_window.restype = wintypes.HWND
    find_window.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
    find_child = user32.FindWindowExW
    find_child.restype = wintypes.HWND
    find_child.argtypes = (wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR)

    def list_view(parent):
        shell_view = find_child(parent, None, "SHELLDLL_DefView", None)
        if shell_view:
            return find_child(shell_view, None, "SysListView32", None)
        return None

    desktop = find_window("Progman", None)
    found = list_view(desktop) if desktop else None
    if found:
        return found

    result = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = (callback_type, wintypes.LPARAM)
    user32.EnumWindows.restype = wintypes.BOOL

    def inspect_window(hwnd, _):
        found_list = list_view(hwnd)
        if found_list:
            result.append(found_list)
            return False
        return True

    user32.EnumWindows(callback_type(inspect_window), 0)
    return result[0] if result else None


def _desktop_icon_centers() -> list[tuple[int, int]]:
    global _desktop_icon_cache
    cached_at, cached_centers = _desktop_icon_cache
    if time.monotonic() - cached_at < 1:
        return cached_centers

    list_view = _find_desktop_list_view()
    if not list_view:
        _desktop_icon_cache = (time.monotonic(), [])
        return []

    process_id = wintypes.DWORD()
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowThreadProcessId(list_view, ctypes.byref(process_id))
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.VirtualAllocEx.argtypes = (wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t,
                                        wintypes.DWORD, wintypes.DWORD)
    kernel32.VirtualAllocEx.restype = ctypes.c_void_p
    kernel32.VirtualFreeEx.argtypes = (wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t,
                                       wintypes.DWORD)
    kernel32.ReadProcessMemory.argtypes = (wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                           ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t))
    kernel32.WriteProcessMemory.argtypes = (wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                            ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t))
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    process = kernel32.OpenProcess(0x0038, False, process_id.value)
    if not process:
        _desktop_icon_cache = (time.monotonic(), [])
        return []

    class ItemRect(ctypes.Structure):
        _fields_ = (("left", wintypes.LONG), ("top", wintypes.LONG),
                    ("right", wintypes.LONG), ("bottom", wintypes.LONG))

    try:
        remote_rect = kernel32.VirtualAllocEx(process, None, ctypes.sizeof(ItemRect), 0x3000, 0x04)
        if not remote_rect:
            _desktop_icon_cache = (time.monotonic(), [])
            return []
        send_message = user32.SendMessageW
        send_message.argtypes = (wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t)
        send_message.restype = ctypes.c_ssize_t
        count = min(max(0, send_message(list_view, 0x1004, 0, 0)), 512)
        write = ctypes.windll.kernel32.WriteProcessMemory
        read = ctypes.windll.kernel32.ReadProcessMemory
        client_to_screen = user32.ClientToScreen
        client_to_screen.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.POINT))
        client_to_screen.restype = wintypes.BOOL
        centers = []
        transferred = ctypes.c_size_t()
        for index in range(count):
            rect = ItemRect(0, 0, 0, 0)
            if not write(process, remote_rect, ctypes.byref(rect), ctypes.sizeof(rect),
                         ctypes.byref(transferred)):
                continue
            if not send_message(list_view, 0x100E, index, remote_rect):
                continue
            if not read(process, remote_rect, ctypes.byref(rect), ctypes.sizeof(rect),
                        ctypes.byref(transferred)):
                continue
            point = wintypes.POINT((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
            if client_to_screen(list_view, ctypes.byref(point)):
                centers.append((point.x, point.y))
        _desktop_icon_cache = (time.monotonic(), centers)
        return centers
    finally:
        if "remote_rect" in locals() and remote_rect:
            kernel32.VirtualFreeEx(process, remote_rect, 0, 0x8000)
        kernel32.CloseHandle(process)


def _interaction_targets(cursor: tuple[int, int], background: bool = False) -> list[Target]:
    """Magnetic targets around the cursor (see ``window_targets``)."""
    return window_targets.interaction_targets(cursor, background, _desktop_icon_centers)


class _MagnetTrace:
    """Diagnostic log of magnetism decisions, enabled by PAWZ_MAGNET_TRACE=<file>.

    One JSON object per line; the file is truncated at startup and capped in size.
    """
    MAX_LINES = 20000

    def __init__(self, path: str | None):
        self.path = path
        self.lines = 0
        self.stream = None

    def write(self, **record) -> None:
        if not self.path or self.lines >= self.MAX_LINES:
            return
        if self.stream is None:
            self.stream = open(self.path, "w", encoding="utf-8")  # noqa: SIM115
            self.stream.write(json.dumps({"header": _environment_report()}) + "\n")
        record["t"] = round(time.perf_counter(), 4)
        self.stream.write(json.dumps(record) + "\n")
        self.lines += 1
        if self.lines % 50 == 0:
            self.stream.flush()


def _environment_report() -> dict:
    report: dict = {}
    try:
        context = user32.GetThreadDpiAwarenessContext()
        report["thread_dpi_awareness"] = user32.GetAwarenessFromDpiAwarenessContext(context)
        report["system_dpi"] = user32.GetDpiForSystem()
        speed = ctypes.c_int()
        user32.SystemParametersInfoW(0x0070, 0, ctypes.byref(speed), 0)  # SPI_GETMOUSESPEED
        accel = (ctypes.c_int * 3)()
        user32.SystemParametersInfoW(0x0003, 0, accel, 0)  # SPI_GETMOUSE
        report["mouse_speed"] = speed.value
        report["enhance_pointer_precision"] = bool(accel[2])
    except (AttributeError, OSError) as exc:
        report["error"] = str(exc)
    return report


_magnet_trace = _MagnetTrace(env("MAGNET_TRACE"))


def _cursor_position(checked: bool = False) -> tuple[int, int]:
    point = wintypes.POINT()
    user32.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
    user32.GetCursorPos.restype = wintypes.BOOL
    if not user32.GetCursorPos(ctypes.byref(point)) and checked:
        raise ctypes.WinError(ctypes.get_last_error())
    return point.x, point.y


def move(dx: float, dy: float, magnet_strength: float = 0, dt: float = 1 / 60,
         full_speed: float = 960.0, background: bool = False) -> str | None:
    """Move the cursor by (dx, dy) pixels; ``dt`` is the time since the previous call.

    ``full_speed`` is the cursor speed in px/s at full stick deflection; it sizes
    the effort needed to leave a magnetic target. ``background`` also makes the
    visible parts of background windows magnetic.

    Returns the magnet event of this step ("captured", "released" or None) so the
    caller can give haptic feedback on the controller that moved the cursor.
    """
    if not (dx or dy):
        # Nothing to move. Running the magnet anyway snapped to any target in range,
        # yanking the cursor back onto a target it had just escaped from.
        return None
    event = None
    if magnet_strength > 0:
        position = _cursor_position(checked=True)
        targets = _interaction_targets(position, background)
        result = _magnet.step(position, dx, dy, magnet_strength, targets,
                              time.perf_counter(), dt * 60, full_speed)
        event = result.event
        if result.warp is not None:
            user32.SetCursorPos.argtypes = (ctypes.c_int, ctypes.c_int)
            user32.SetCursorPos.restype = wintypes.BOOL
            if not user32.SetCursorPos(*result.warp):
                raise ctypes.WinError(ctypes.get_last_error())
            _pointer_residual.reset()
        if _magnet_trace.path:
            _magnet_trace.write(pos=position, d=(round(dx, 3), round(dy, 3)),
                                out=[round(v, 3) for v in result.delta], warp=result.warp,
                                event=event, captured=_magnet.captured,
                                targets=_nearest(targets, position))
        if result.warp is not None:
            return event
        dx, dy = result.delta
    elif _magnet.captured is not None:
        _magnet.reset()
    step_x, step_y = _pointer_residual.take(dx, dy)
    if step_x or step_y:
        send_mouse(MOUSEEVENTF_MOVE, step_x, step_y)
    return event


def _nearest(targets: list[Target], position: tuple[int, int], limit: int = 6) -> list:
    return sorted(targets, key=lambda t: math.dist(position, (t[0], t[1])))[:limit]


def scroll(amount: int) -> None:
    send_mouse(MOUSEEVENTF_WHEEL, data=int(amount * 120))

def active_process() -> str:
    """Lowercase executable name of the foreground window, cached per PID."""
    global _last_process
    hwnd = user32.GetForegroundWindow()
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value and pid.value == _last_process[0]:
        return _last_process[1]
    try:
        name = psutil.Process(pid.value).name().lower()
    except (psutil.Error, OSError):
        return ""
    _last_process = (pid.value, name)
    return name

class _MonitorInfo(ctypes.Structure):
    _fields_ = (("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD))


def foreground_fullscreen() -> bool:
    """Whether the foreground window is exactly its monitor (games, videos).

    A maximized window is not: it overflows the monitor by its invisible borders.
    """
    hwnd = user32.GetForegroundWindow()
    if not hwnd or user32.IsZoomed(hwnd):
        return False
    rect = wintypes.RECT()
    user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user32.MonitorFromWindow.argtypes = (wintypes.HWND, wintypes.DWORD)
    user32.MonitorFromWindow.restype = wintypes.HANDLE
    user32.GetMonitorInfoW.argtypes = (wintypes.HANDLE, ctypes.POINTER(_MonitorInfo))
    monitor = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
    info = _MonitorInfo(ctypes.sizeof(_MonitorInfo))
    if not (user32.GetWindowRect(hwnd, ctypes.byref(rect))
            and user32.GetMonitorInfoW(monitor, ctypes.byref(info))):
        return False
    screen = info.rcMonitor
    return (rect.left, rect.top, rect.right, rect.bottom) == (
        screen.left, screen.top, screen.right, screen.bottom)


def open_keyboard() -> None:
    keyboard = Path(os.environ["WINDIR"]) / "System32" / "osk.exe"
    if not keyboard.is_file():
        raise FileNotFoundError(f"Windows on-screen keyboard not found: {keyboard}")
    os.startfile(str(keyboard))

class WindowsOutput:
    """``OutputSink`` injecting into Windows (see ``pawz.engine.actions``)."""

    def mouse_down(self, button: str) -> None:
        mouse_button_down(button)

    def mouse_up(self, button: str) -> None:
        mouse_button_up(button)

    def click(self, button: str) -> None:
        click(button)

    def key_combo(self, keys: str) -> None:
        key_combo(keys)

    def move(self, dx: float, dy: float, magnet_strength: float = 0, dt: float = 1 / 60,
             full_speed: float = 960.0, background: bool = False) -> str | None:
        return move(dx, dy, magnet_strength, dt, full_speed, background)

    def scroll(self, steps: int) -> None:
        scroll(steps)


def perform(action: str, keys: str = "") -> None:
    actions.execute(action, keys, WindowsOutput())
