"""Reliable RIFT window input from Python via ctypes/win32.

Resolves the game window by PID / process name / HWND (never title alone),
verifies the HWND belongs to that process, acquires and holds foreground
focus while sending, then optionally restores the previous foreground window.

Modes:
  - momentary key tap / held movement key (SendInput, foreground)
  - macro hotkeys (modifier + key)
  - scripted chat command (open chat, type, Enter)

Reference behavior borrowed conceptually from 360madden/riftreader
(scripts/post-rift-key.ps1) but implemented in pure Python.
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102
SW_RESTORE = 9
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
MAPVK_VK_TO_VSC = 0

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_RETURN = 0x0D

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wt.WORD),
        ("wScan", wt.WORD),
        ("dwFlags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("union", INPUTUNION)]


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("flags", wt.DWORD),
        ("hwndActive", wt.HWND),
        ("hwndFocus", wt.HWND),
        ("hwndCapture", wt.HWND),
        ("hwndMenuOwner", wt.HWND),
        ("hwndMoveSize", wt.HWND),
        ("hwndCaret", wt.HWND),
        ("rcCaret", wt.RECT),
    ]


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("cntUsage", wt.DWORD),
        ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", wt.DWORD),
        ("cntThreads", wt.DWORD),
        ("th32ParentProcessID", wt.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wt.DWORD),
        ("szExeFile", wt.CHAR * 260),
    ]


def _set_argtypes():
    user32.IsWindow.argtypes = [wt.HWND]
    user32.IsWindow.restype = wt.BOOL
    user32.GetWindowTextLengthW.argtypes = [wt.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
    user32.GetWindowThreadProcessId.restype = wt.DWORD
    user32.GetWindow.argtypes = [wt.HWND, wt.UINT]
    user32.GetWindow.restype = wt.HWND
    user32.IsWindowVisible.argtypes = [wt.HWND]
    user32.IsWindowVisible.restype = wt.BOOL
    user32.EnumWindows.argtypes = [
        ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM),
        wt.LPARAM,
    ]
    user32.EnumWindows.restype = wt.BOOL
    user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    user32.PostMessageW.restype = wt.BOOL
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wt.HWND
    user32.SetForegroundWindow.argtypes = [wt.HWND]
    user32.SetForegroundWindow.restype = wt.BOOL
    user32.BringWindowToTop.argtypes = [wt.HWND]
    user32.BringWindowToTop.restype = wt.BOOL
    user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wt.BOOL
    user32.AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]
    user32.AttachThreadInput.restype = wt.BOOL
    user32.GetGUIThreadInfo.argtypes = [wt.DWORD, ctypes.POINTER(GUITHREADINFO)]
    user32.GetGUIThreadInfo.restype = wt.BOOL
    user32.VkKeyScanW.argtypes = [wt.WCHAR]
    user32.VkKeyScanW.restype = ctypes.c_short
    user32.MapVirtualKeyW.argtypes = [wt.UINT, wt.UINT]
    user32.MapVirtualKeyW.restype = wt.UINT
    user32.SendInput.argtypes = [wt.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.SendInput.restype = wt.UINT
    kernel32.GetCurrentThreadId.argtypes = []
    kernel32.GetCurrentThreadId.restype = wt.DWORD
    kernel32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wt.HANDLE
    kernel32.Process32First.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
    kernel32.Process32First.restype = wt.BOOL
    kernel32.Process32Next.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
    kernel32.Process32Next.restype = wt.BOOL
    kernel32.CloseHandle.argtypes = [wt.HANDLE]
    kernel32.CloseHandle.restype = wt.BOOL


_set_argtypes()


def _as_hwnd(value: str | int) -> wt.HWND:
    if isinstance(value, int):
        return wt.HWND(value)
    text = str(value).strip()
    if text.lower().startswith("0x"):
        return wt.HWND(int(text, 16))
    return wt.HWND(int(text))


def window_title(hwnd: wt.HWND) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def owner_pid(hwnd: wt.HWND) -> int:
    pid = wt.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _resolve_pids_by_name(name: str) -> list[int]:
    exe = name.lower()
    if not exe.endswith(".exe"):
        exe = exe + ".exe"
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    if int(snapshot) == -1:
        raise RuntimeError("Could not snapshot processes")
    try:
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        pids: list[int] = []
        if kernel32.Process32First(snapshot, ctypes.byref(entry)):
            while True:
                if entry.szExeFile.decode("ascii", "ignore").lower() == exe:
                    pids.append(entry.th32ProcessID)
                if not kernel32.Process32Next(snapshot, ctypes.byref(entry)):
                    break
        return pids
    finally:
        kernel32.CloseHandle(snapshot)


def _find_main_window(pid: int) -> wt.HWND:
    result = wt.HWND(0)
    owner_check = wt.DWORD(0)

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def callback(hwnd, lparam):
        nonlocal result
        if not user32.IsWindow(hwnd):
            return True
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner_check))
        if owner_check.value != pid:
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        if user32.GetWindow(hwnd, 4):
            return True
        result = hwnd
        return False

    user32.EnumWindows(callback, 0)
    return result


def resolve_window(
    process_name: str | None = None,
    pid: int | None = None,
    hwnd: str | int | None = None,
    title_contains: str | None = None,
    allow_first_match: bool = False,
) -> tuple[wt.HWND, int]:
    target_hwnd: wt.HWND | None = None
    target_pid: int | None = None

    if hwnd is not None:
        target_hwnd = _as_hwnd(hwnd)
        if not user32.IsWindow(target_hwnd):
            raise ValueError(f"HWND {hwnd} is not a valid window")
        target_pid = owner_pid(target_hwnd)
    elif pid is not None:
        target_pid = int(pid)
        target_hwnd = _find_main_window(target_pid)
    elif process_name is not None:
        pids = _resolve_pids_by_name(process_name)
        if not pids:
            raise ValueError(f"No process named {process_name} found")
        if len(pids) > 1 and not allow_first_match:
            raise ValueError(
                f"Process name {process_name} matched multiple PIDs {pids}; pass --pid or --hwnd to disambiguate"
            )
        target_pid = pids[0]
        target_hwnd = _find_main_window(target_pid)
    else:
        raise ValueError("Provide --process, --pid, or --hwnd")

    if target_hwnd is None or int(target_hwnd) == 0:
        raise ValueError("Resolved process has no main window handle")

    if owner_pid(target_hwnd) != target_pid:
        raise ValueError(
            f"Resolved HWND 0x{target_hwnd:X} belongs to PID {owner_pid(target_hwnd)}, not requested PID {target_pid}"
        )

    if process_name is not None:
        resolved_pids = _resolve_pids_by_name(process_name)
        if target_pid not in resolved_pids:
            raise ValueError(f"HWND 0x{target_hwnd:X} PID {target_pid} is not {process_name}")

    if title_contains:
        title = window_title(target_hwnd)
        if title_contains.lower() not in title.lower():
            raise ValueError(f"Window title {title!r} does not contain {title_contains!r}")

    return target_hwnd, target_pid


def effective_target(hwnd: wt.HWND, pid: int) -> wt.HWND:
    thread_id = user32.GetWindowThreadProcessId(hwnd, None)
    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(GUITHREADINFO)
    if not user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)):
        return hwnd
    if info.hwndFocus and info.hwndFocus != 0:
        if owner_pid(info.hwndFocus) == pid:
            return info.hwndFocus
    return hwnd


def focus_window(hwnd: wt.HWND) -> wt.HWND:
    previous = user32.GetForegroundWindow()
    if previous == hwnd:
        return previous
    current = kernel32.GetCurrentThreadId()
    fg_thread = user32.GetWindowThreadProcessId(previous, None) if previous else 0
    target_thread = user32.GetWindowThreadProcessId(hwnd, None)
    if fg_thread and fg_thread != current:
        user32.AttachThreadInput(current, fg_thread, True)
    if target_thread and target_thread != current:
        user32.AttachThreadInput(current, target_thread, True)
    try:
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.25)
    finally:
        if target_thread and target_thread != current:
            user32.AttachThreadInput(current, target_thread, False)
        if fg_thread and fg_thread != current:
            user32.AttachThreadInput(current, fg_thread, False)
    return previous


def restore_foreground(hwnd: wt.HWND) -> None:
    if not hwnd or int(hwnd) == 0:
        return
    current = kernel32.GetCurrentThreadId()
    fg_thread = user32.GetWindowThreadProcessId(hwnd, None)
    if fg_thread and fg_thread != current:
        user32.AttachThreadInput(current, fg_thread, True)
    try:
        user32.SetForegroundWindow(hwnd)
    finally:
        if fg_thread and fg_thread != current:
            user32.AttachThreadInput(current, fg_thread, False)


def is_foreground(pid: int) -> bool:
    fg = user32.GetForegroundWindow()
    if int(fg) == 0:
        return False
    return owner_pid(fg) == pid


def _send_input(vk: int, scan: int, flags: int) -> None:
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.union.ki.wVk = vk
    inp.union.ki.wScan = scan
    inp.union.ki.dwFlags = flags
    inp.union.ki.time = 0
    inp.union.ki.dwExtraInfo = None
    size = ctypes.sizeof(INPUT)
    sent = user32.SendInput(1, ctypes.byref(inp), size)
    if sent != 1:
        err = kernel32.GetLastError()
        raise RuntimeError(
            f"SendInput sent {sent} of 1 (vk={vk:#x}, scan={scan:#x}, flags={flags:#x}, lastError={err})"
        )


def send_input_key(vk: int, keyup: bool = False) -> None:
    scan = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
    flags = KEYEVENTF_KEYUP if keyup else 0
    _send_input(vk, scan, flags)


def send_input_unicode(char: str, keyup: bool = False) -> None:
    flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if keyup else 0)
    _send_input(0, ord(char), flags)


@contextmanager
def _attached(hwnd: wt.HWND) -> Iterator[None]:
    current = kernel32.GetCurrentThreadId()
    fg = user32.GetForegroundWindow()
    fg_thread = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    target_thread = user32.GetWindowThreadProcessId(hwnd, None)
    attached: list[int] = []
    if fg_thread and fg_thread != current:
        user32.AttachThreadInput(current, fg_thread, True)
        attached.append(fg_thread)
    if target_thread and target_thread != current:
        user32.AttachThreadInput(current, target_thread, True)
        attached.append(target_thread)
    try:
        yield
    finally:
        for t in attached:
            user32.AttachThreadInput(current, t, False)


def _key_lparam(vk: int, keyup: bool) -> wt.LPARAM:
    scan = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
    value = 1 | (scan << 16)
    if keyup:
        value |= 0xC0000000
    return wt.LPARAM(value)


def post_key(hwnd: wt.HWND, vk: int, keyup: bool = False) -> None:
    msg = WM_KEYUP if keyup else WM_KEYDOWN
    user32.PostMessageW(hwnd, msg, wt.WPARAM(vk), _key_lparam(vk, keyup))


def post_char(hwnd: wt.HWND, char: str) -> None:
    user32.PostMessageW(hwnd, WM_CHAR, wt.WPARAM(ord(char)), wt.LPARAM(0))


def post_text(hwnd: wt.HWND, text: str) -> None:
    for char in text:
        post_char(hwnd, char)


def resolve_vk(key: str) -> tuple[int, int]:
    named = {
        "SPACE": 0x20,
        "LEFT": 0x25,
        "UP": 0x26,
        "RIGHT": 0x27,
        "DOWN": 0x28,
        "ENTER": VK_RETURN,
        "RETURN": VK_RETURN,
        "TAB": 0x09,
        "ESC": 0x1B,
        "ESCAPE": 0x1B,
        "F1": 0x70,
        "F2": 0x71,
        "F3": 0x72,
        "F4": 0x73,
        "F5": 0x74,
        "F6": 0x75,
        "F7": 0x76,
        "F8": 0x77,
        "F9": 0x78,
        "F10": 0x79,
        "F11": 0x7A,
        "F12": 0x7B,
        "F13": 0x7C,
        "F14": 0x7D,
        "F15": 0x7E,
        "F16": 0x7F,
        "F17": 0x80,
        "F18": 0x81,
        "F19": 0x82,
        "F20": 0x83,
        "F21": 0x84,
        "F22": 0x85,
        "F23": 0x86,
        "F24": 0x87,
        "BACK": 0x08,
        "BACKSPACE": 0x08,
        "DELETE": 0x2E,
        "INSERT": 0x2D,
        "HOME": 0x24,
        "END": 0x23,
        "PRIOR": 0x21,
        "NEXT": 0x22,
    }
    normalized = key.strip().upper()
    if normalized in named:
        return named[normalized], 0
    if normalized.startswith("0X") or normalized.startswith("VK"):
        raw = normalized[2:] if normalized.startswith("VK") else normalized[2:]
        return int(raw, 16), 0
    if len(key) != 1:
        raise ValueError("Single character key required unless a named key")
    vk_scan = user32.VkKeyScanW(key[0])
    if vk_scan == -1:
        raise ValueError(f"No virtual-key mapping for {key!r}")
    return vk_scan & 0xFF, (vk_scan >> 8) & 0xFF


def press_key(
    hwnd: wt.HWND,
    key: str,
    hold_ms: int = 250,
    require_foreground: bool = True,
    inter_delay_ms: int = 20,
    method: str = "sendinput",
) -> None:
    vk, shift_state = resolve_vk(key)
    if method == "post":
        target = effective_target(hwnd, owner_pid(hwnd))
        modifiers = []
        if shift_state & 1:
            modifiers.append(VK_SHIFT)
        if shift_state & 2:
            modifiers.append(VK_CONTROL)
        if shift_state & 4:
            modifiers.append(VK_MENU)
        for mod in modifiers:
            post_key(target, mod)
            time.sleep(inter_delay_ms / 1000.0)
        post_key(target, vk)
        time.sleep(hold_ms / 1000.0)
        post_key(target, vk, keyup=True)
        for mod in reversed(modifiers):
            time.sleep(inter_delay_ms / 1000.0)
            post_key(target, mod, keyup=True)
        return
    if require_foreground:
        focus_window(hwnd)
        if not is_foreground(owner_pid(hwnd)):
            focus_window(hwnd)
            if not is_foreground(owner_pid(hwnd)):
                raise RuntimeError("Target is not foreground; aborting key send")
    with _attached(hwnd):
        modifiers = []
        if shift_state & 1:
            modifiers.append(VK_SHIFT)
        if shift_state & 2:
            modifiers.append(VK_CONTROL)
        if shift_state & 4:
            modifiers.append(VK_MENU)
        for mod in modifiers:
            send_input_key(mod)
            time.sleep(inter_delay_ms / 1000.0)
        send_input_key(vk)
        time.sleep(hold_ms / 1000.0)
        send_input_key(vk, keyup=True)
        for mod in reversed(modifiers):
            time.sleep(inter_delay_ms / 1000.0)
            send_input_key(mod, keyup=True)


def type_text(
    hwnd: wt.HWND,
    text: str,
    per_char_delay_ms: int = 30,
    require_foreground: bool = True,
    method: str = "sendinput",
) -> None:
    if method == "post":
        target = effective_target(hwnd, owner_pid(hwnd))
        for char in text:
            post_char(target, char)
            time.sleep(per_char_delay_ms / 1000.0)
        return
    if require_foreground:
        focus_window(hwnd)
    with _attached(hwnd):
        for char in text:
            send_input_unicode(char)
            time.sleep(per_char_delay_ms / 1000.0)
            send_input_unicode(char, keyup=True)
            time.sleep(per_char_delay_ms / 1000.0)


def send_command(
    hwnd: wt.HWND,
    command: str,
    open_chat: bool = True,
    require_foreground: bool = True,
    char_delay_ms: int = 30,
    method: str = "sendinput",
) -> None:
    if method == "post":
        if open_chat:
            target = effective_target(hwnd, owner_pid(hwnd))
            post_key(target, VK_RETURN)
            time.sleep(0.12)
            post_key(target, VK_RETURN, keyup=True)
            time.sleep(0.12)
        target = effective_target(hwnd, owner_pid(hwnd))
        post_text(target, command)
        time.sleep(0.12)
        post_key(target, VK_RETURN)
        time.sleep(0.08)
        post_key(target, VK_RETURN, keyup=True)
        return
    if require_foreground:
        focus_window(hwnd)
    with _attached(hwnd):
        if open_chat:
            send_input_key(VK_RETURN)
            time.sleep(0.12)
            send_input_key(VK_RETURN, keyup=True)
            time.sleep(0.12)
        type_text(hwnd, command, per_char_delay_ms=char_delay_ms, require_foreground=False)
        send_input_key(VK_RETURN)
        time.sleep(0.12)
        send_input_key(VK_RETURN, keyup=True)


@contextmanager
def held_focus(hwnd: wt.HWND, restore: bool = True) -> Iterator[wt.HWND]:
    previous = focus_window(hwnd)
    try:
        yield hwnd
    finally:
        if restore:
            restore_foreground(previous)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send reliable input to the RIFT window")
    parser.add_argument("--process", help="Process name (e.g. rift_x64)")
    parser.add_argument("--pid", type=int, help="Target process id")
    parser.add_argument("--hwnd", help="Target window handle (decimal or 0x...)")
    parser.add_argument("--title-contains", help="Optional window title substring")
    parser.add_argument("--allow-first-match", action="store_true")
    parser.add_argument("--key", help="Single key / named key to tap (e.g. W, SPACE)")
    parser.add_argument("--hold", type=int, default=250, help="Hold milliseconds")
    parser.add_argument("--command", help="Scripted chat command (e.g. /reloadui)")
    parser.add_argument("--text", help="Raw text to type into the focused window")
    parser.add_argument(
        "--no-foreground", action="store_true", help="Send without forcing foreground (post-only style)"
    )
    parser.add_argument(
        "--method",
        choices=["sendinput", "post"],
        default="sendinput",
        help="sendinput=foreground SendInput; post=no-focus PostMessage",
    )
    parser.add_argument("--no-restore", action="store_true", help="Do not restore previous foreground window")
    parser.add_argument("--broker", action="store_true", help="Use localhost broker instead of direct ctypes")
    parser.add_argument(
        "--broker-url", default="http://127.0.0.1:8769", help="Broker URL (default: http://127.0.0.1:8769)"
    )
    args = parser.parse_args(argv)

    if args.broker:
        return _broker_main(args)

    if not (args.process or args.pid or args.hwnd):
        parser.error("Provide --process, --pid, or --hwnd")
    if not (args.key or args.command or args.text):
        parser.error("Provide --key, --command, or --text")

    hwnd, pid = resolve_window(
        process_name=args.process,
        pid=args.pid,
        hwnd=args.hwnd,
        title_contains=args.title_contains,
        allow_first_match=args.allow_first_match,
    )
    require_fg = not args.no_foreground
    restore = not args.no_restore

    with held_focus(hwnd, restore=restore):
        if args.key:
            press_key(hwnd, args.key, hold_ms=args.hold, require_foreground=require_fg, method=args.method)
        if args.text:
            type_text(hwnd, args.text, require_foreground=require_fg, method=args.method)
        if args.command:
            send_command(hwnd, args.command, require_foreground=require_fg, method=args.method)

    print(f"OK hwnd=0x{hwnd:X} pid={pid}")
    return 0


def _broker_main(args: argparse.Namespace) -> int:
    import json
    import urllib.error
    import urllib.request

    base = args.broker_url

    def call(method: str, path: str, body: dict | None = None) -> dict:
        url = f"{base}{path}"
        data = json.dumps(body or {}).encode("utf-8") if method == "POST" else None
        req = urllib.request.Request(url, data=data, method=method)
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except urllib.error.URLError as e:
            return {"ok": False, "error": str(e)}

    health = call("GET", "/health")
    if not health.get("ok"):
        print(f"Broker not running at {base}: {health.get('error')}", file=sys.stderr)
        print("Start broker: scripts\\start-rift-broker.cmd", file=sys.stderr)
        return 1

    if args.key:
        result = call("POST", "/key", {"key": args.key, "hold_ms": args.hold, "method": args.method})
    elif args.text:
        result = call("POST", "/text", {"text": args.text, "method": args.method})
    elif args.command:
        result = call("POST", "/command", {"command": args.command, "open_chat": True, "method": args.method})
    else:
        raise SystemExit("Provide --key, --command, or --text with --broker")

    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
