"""Localhost input broker for RIFT.

Run this in your interactive (elevated) terminal session:
    python scripts/rift_broker.py [--port 8769] [--process rift_x64]

It starts an HTTP server on 127.0.0.1 that accepts JSON commands and
executes them against the RIFT window. The AI (or any local client)
calls it via simple HTTP POST — no cross-session SendInput issues.

Endpoints:
    GET  /health          -> {status, hwnd, pid, title, method}
    POST /resolve         -> re-resolve RIFT window (after restart)
    POST /key             -> {"key": "W", "hold_ms": 250, "method": "sendinput"}
    POST /text            -> {"text": "hello world"}
    POST /command         -> {"command": "/reloadui", "open_chat": true}
    POST /focus           -> acquire foreground focus
    POST /restore         -> restore previous foreground window
    POST /resize          -> {"size": "720p"} or {"size": "1280x720"}

All POST bodies are JSON. Returns JSON with {"ok": true, ...} or {"ok": false, "error": "..."}.

Usage:
    python scripts/rift_broker.py
    python scripts/rift_broker.py --port 8769 --process rift_x64
"""

from __future__ import annotations

import argparse
import base64
import ctypes
import ctypes.wintypes as wt
import http.server
import json
import os
import struct
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rift_input import (
    focus_window,
    press_key,
    resolve_window,
    restore_foreground,
    send_command,
    type_text,
    window_title,
)

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

_MIN_WIDTH = 640
_MIN_HEIGHT = 360
_MAX_WIDTH = 1920
_MAX_HEIGHT = 1080
_SWP_NOZORDER = 0x0004
_SWP_NOACTIVATE = 0x0010
_SWP_FRAMECHANGED = 0x0020

_RESIZE_PRESETS: dict[str, tuple[int, int]] = {
    "360p": (640, 360),
    "540p": (960, 540),
    "576p": (1024, 576),
    "720p": (1280, 720),
    "900p": (1600, 900),
    "1080p": (1920, 1080),
}

_RESIZE_ALIASES: dict[str, str] = {
    "default": "360p",
    "min": "360p",
    "minimum": "360p",
    "640x360": "360p",
    "960x540": "540p",
    "1024x576": "576p",
    "1280x720": "720p",
    "1600x900": "900p",
    "1920x1080": "1080p",
}

try:
    user32.SetProcessDPIAware()
except AttributeError:
    pass

_rift_hwnd: wt.HWND | None = None
_rift_pid: int | None = None
_previous_foreground: wt.HWND | None = None
_lock = threading.Lock()
_method: str = "post"
_log_file = None


def _log(entry: dict) -> None:
    if _log_file is None:
        return
    entry["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        with open(_log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def _capture_window(hwnd: wt.HWND) -> bytes | None:
    try:
        rect = wt.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if width <= 0 or height <= 0:
            return None
        hdc_window = user32.GetDC(hwnd)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_window)
        hbitmap = gdi32.CreateCompatibleBitmap(hdc_window, width, height)
        gdi32.SelectObject(hdc_mem, hbitmap)
        result = user32.PrintWindow(hwnd, hdc_mem, 2)
        if not result:
            gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_window, 0, 0, 0x00CC0020)
        bmp_size = 40 + width * height * 4
        bmp_data = (ctypes.c_ubyte * bmp_size)()
        struct.pack_into("<I", bmp_data, 0, 40)
        struct.pack_into("<i", bmp_data, 4, width)
        struct.pack_into("<i", bmp_data, 8, height)
        struct.pack_into("<H", bmp_data, 12, 1)
        struct.pack_into("<H", bmp_data, 14, 32)
        struct.pack_into("<I", bmp_data, 20, width * height * 4)
        gdi32.GetBitmapBits(hbitmap, width * height * 4, ctypes.byref(bmp_data, 40))
        gdi32.DeleteObject(hbitmap)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(hwnd, hdc_window)
        return bytes(bmp_data)
    except Exception:
        return None


def _resolve() -> dict:
    global _rift_hwnd, _rift_pid
    try:
        _rift_hwnd, _rift_pid = resolve_window(process_name=_args.process, pid=_args.pid)
        return {
            "ok": True,
            "hwnd": f"0x{_rift_hwnd:X}",
            "pid": _rift_pid,
            "title": window_title(_rift_hwnd),
            "method": _method,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _handle_key(body: dict) -> dict:
    key = body.get("key")
    if not key:
        return {"ok": False, "error": "missing 'key'"}
    hold_ms = int(body.get("hold_ms", 250))
    method = body.get("method", _method)
    try:
        press_key(_rift_hwnd, key, hold_ms=hold_ms, require_foreground=False, method=method)
        result = {"ok": True, "key": key, "hold_ms": hold_ms, "method": method}
        _log({"action": "key", **result})
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _handle_text(body: dict) -> dict:
    text = body.get("text")
    if text is None:
        return {"ok": False, "error": "missing 'text'"}
    method = body.get("method", _method)
    try:
        type_text(_rift_hwnd, str(text), require_foreground=False, method=method)
        result = {"ok": True, "length": len(str(text)), "method": method}
        _log({"action": "text", "length": len(str(text)), "method": method})
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _handle_command(body: dict) -> dict:
    command = body.get("command")
    if not command:
        return {"ok": False, "error": "missing 'command'"}
    open_chat = bool(body.get("open_chat", True))
    method = body.get("method", _method)
    try:
        send_command(
            _rift_hwnd,
            command,
            open_chat=open_chat,
            require_foreground=False,
            method=method,
        )
        result = {"ok": True, "command": command, "open_chat": open_chat, "method": method}
        _log({"action": "command", "command": command, "open_chat": open_chat, "method": method})
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _handle_focus() -> dict:
    global _previous_foreground
    try:
        _previous_foreground = focus_window(_rift_hwnd)
        return {"ok": True, "previous": f"0x{_previous_foreground:X}" if _previous_foreground else None}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _handle_restore() -> dict:
    global _previous_foreground
    try:
        restore_foreground(_previous_foreground)
        _previous_foreground = None
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _handle_memory(body: dict) -> dict:
    address = body.get("address")
    size = int(body.get("size", 64))
    if not address:
        return {"ok": False, "error": "missing 'address'"}
    try:
        addr = int(address, 16) if isinstance(address, str) else int(address)
        kernel32 = ctypes.windll.kernel32
        PROCESS_VM_READ = 0x0010
        handle = kernel32.OpenProcess(PROCESS_VM_READ, False, _rift_pid)
        if not handle:
            return {"ok": False, "error": "OpenProcess failed"}
        buf = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t(0)
        kernel32.ReadProcessMemory(handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(bytes_read))
        kernel32.CloseHandle(handle)
        data = buf.raw[: bytes_read.value]
        return {
            "ok": True,
            "address": f"0x{addr:X}",
            "size": bytes_read.value,
            "data": base64.b64encode(data).decode("ascii"),
            "hex": data.hex(),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _parse_resize_size(size_str: str) -> tuple[int, int]:
    raw = size_str.strip().casefold()
    alias = _RESIZE_ALIASES.get(raw, raw)
    if alias in _RESIZE_PRESETS:
        return _RESIZE_PRESETS[alias]
    if "x" not in raw:
        known = ", ".join(_RESIZE_PRESETS)
        raise ValueError(f"unknown preset {size_str!r}. Known: {known}")
    left, right = raw.split("x", 1)
    width, height = int(left), int(right)
    if width < _MIN_WIDTH or height < _MIN_HEIGHT:
        raise ValueError(f"minimum is {_MIN_WIDTH}x{_MIN_HEIGHT}")
    if width > _MAX_WIDTH or height > _MAX_HEIGHT:
        raise ValueError(f"maximum is {_MAX_WIDTH}x{_MAX_HEIGHT}")
    if width * 9 != height * 16:
        raise ValueError(f"must be exact 16:9, got {width}x{height}")
    return width, height


def _handle_resize(body: dict) -> dict:
    size_str = body.get("size", "360p")
    try:
        width, height = _parse_resize_size(size_str)
    except (ValueError, KeyError) as e:
        return {"ok": False, "error": str(e)}

    hwnd = _rift_hwnd
    if not hwnd:
        return {"ok": False, "error": "no RIFT window resolved"}

    try:
        outer = wt.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(outer))
        client = wt.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(client))

        before_outer_w = int(outer.right - outer.left)
        before_outer_h = int(outer.bottom - outer.top)
        before_client_w = int(client.right - client.left)
        before_client_h = int(client.bottom - client.top)

        border_w = before_outer_w - before_client_w
        border_h = before_outer_h - before_client_h
        target_outer_w = width + border_w
        target_outer_h = height + border_h

        for _ in range(2):
            ok = user32.SetWindowPos(
                hwnd,
                None,
                int(outer.left),
                int(outer.top),
                target_outer_w,
                target_outer_h,
                _SWP_NOZORDER | _SWP_NOACTIVATE | _SWP_FRAMECHANGED,
            )
            if not ok:
                return {"ok": False, "error": "SetWindowPos failed"}
            time.sleep(0.15)

            user32.GetClientRect(hwnd, ctypes.byref(client))
            actual_w = int(client.right - client.left)
            actual_h = int(client.bottom - client.top)
            if actual_w == width and actual_h == height:
                break

            user32.GetWindowRect(hwnd, ctypes.byref(outer))
            border_w = int(outer.right - outer.left) - actual_w
            border_h = int(outer.bottom - outer.top) - actual_h
            target_outer_w = width + border_w
            target_outer_h = height + border_h

        user32.GetWindowRect(hwnd, ctypes.byref(outer))
        user32.GetClientRect(hwnd, ctypes.byref(client))

        return {
            "ok": True,
            "requested": f"{width}x{height}",
            "before": {
                "client": f"{before_client_w}x{before_client_h}",
                "outer": f"{before_outer_w}x{before_outer_h}",
            },
            "after": {
                "client": f"{int(client.right - client.left)}x{int(client.bottom - client.top)}",
                "outer": f"{int(outer.right - outer.left)}x{int(outer.bottom - outer.top)}",
            },
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


class BrokerHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._respond(
                {
                    "ok": True,
                    "hwnd": f"0x{_rift_hwnd:X}",
                    "pid": _rift_pid,
                    "title": window_title(_rift_hwnd),
                    "method": _method,
                }
            )
        elif self.path == "/screenshot":
            self._handle_screenshot()
        else:
            self._respond({"ok": False, "error": f"unknown path {self.path}"}, 404)

    def do_POST(self):
        body = self._read_body()
        if self.path == "/resolve":
            with _lock:
                self._respond(_resolve())
        elif self.path == "/key":
            with _lock:
                self._respond(_handle_key(body))
        elif self.path == "/text":
            with _lock:
                self._respond(_handle_text(body))
        elif self.path == "/command":
            with _lock:
                self._respond(_handle_command(body))
        elif self.path == "/focus":
            with _lock:
                self._respond(_handle_focus())
        elif self.path == "/restore":
            with _lock:
                self._respond(_handle_restore())
        elif self.path == "/memory":
            with _lock:
                self._respond(_handle_memory(body))
        elif self.path == "/resize":
            with _lock:
                self._respond(_handle_resize(body))
        else:
            self._respond({"ok": False, "error": f"unknown path {self.path}"}, 404)

    def _handle_screenshot(self):
        try:
            bmp_data = _capture_window(_rift_hwnd)
            if bmp_data is None:
                self._respond({"ok": False, "error": "failed to capture window"})
                return
            b64 = base64.b64encode(bmp_data).decode("ascii")
            self._respond({"ok": True, "format": "bmp", "data": b64, "hwnd": f"0x{_rift_hwnd:X}", "pid": _rift_pid})
        except Exception as e:
            self._respond({"ok": False, "error": str(e)})

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def _respond(self, data: dict, status: int = 200):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        print(f"[broker] {args[0]}", file=sys.stderr)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RIFT localhost input broker")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8769)
    parser.add_argument("--process", default="rift_x64")
    parser.add_argument("--pid", type=int, default=None)
    parser.add_argument("--method", choices=["sendinput", "post"], default="post")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    global _args, _method, _log_file
    _args = _parse_args(argv)
    _method = _args.method
    _log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rift-broker.log")

    with _lock:
        result = _resolve()
    if not result.get("ok"):
        print(f"[broker] FAILED to resolve RIFT window: {result.get('error')}", file=sys.stderr)
        print("[broker] Make sure RIFT is running, then use POST /resolve to retry.", file=sys.stderr)
    else:
        print(f"[broker] RIFT resolved: hwnd={result['hwnd']} pid={result['pid']} title={result['title']!r}")

    server = http.server.HTTPServer((_args.host, _args.port), BrokerHandler)
    print(f"[broker] Listening on http://{_args.host}:{_args.port}")
    print(
        "[broker] Endpoints: GET /health, POST /resolve, POST /key, POST /text, POST /command, POST /focus, POST /restore, POST /resize"
    )
    print("[broker] Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[broker] Shutting down.")
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
