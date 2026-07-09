"""Thin client for the RIFT localhost input broker.

Call from the AI or any Python script — no dependencies beyond stdlib.

Usage:
    python scripts/rift_broker_client.py health
    python scripts/rift_broker_client.py resolve
    python scripts/rift_broker_client.py key W --hold 300
    python scripts/rift_broker_client.py text "hello world"
    python scripts/rift_broker_client.py command "/reloadui"
    python scripts/rift_broker_client.py focus
    python scripts/rift_broker_client.py restore
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8769"


def call(method: str, path: str, body: dict | None = None, base: str = DEFAULT_URL, auto_resolve: bool = True) -> dict:
    url = f"{base}{path}"
    data = json.dumps(body or {}).encode("utf-8") if method == "POST" else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        if auto_resolve and path != "/resolve" and path != "/health":
            health = call("GET", "/health", base=base, auto_resolve=False)
            if not health.get("ok"):
                resolve = call("POST", "/resolve", base=base, auto_resolve=False)
                if resolve.get("ok"):
                    return call(method, path, body, base=base, auto_resolve=False)
        return {"ok": False, "error": str(e)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RIFT broker client")
    parser.add_argument(
        "action", choices=["health", "resolve", "key", "text", "command", "focus", "restore", "screenshot", "memory"]
    )
    parser.add_argument("value", nargs="?", help="Key/text/command value or memory address")
    parser.add_argument("--hold", type=int, default=250, help="Hold ms for key")
    parser.add_argument("--method", default="post", choices=["sendinput", "post"])
    parser.add_argument("--no-chat", action="store_true", help="Don't open chat before command")
    parser.add_argument("--base", default=DEFAULT_URL, help="Broker URL")
    parser.add_argument("--size", type=int, default=64, help="Memory read size")
    args = parser.parse_args(argv)

    if args.action == "health":
        result = call("GET", "/health", base=args.base)
    elif args.action == "resolve":
        result = call("POST", "/resolve", base=args.base)
    elif args.action == "focus":
        result = call("POST", "/focus", base=args.base)
    elif args.action == "restore":
        result = call("POST", "/restore", base=args.base)
    elif args.action == "key":
        if not args.value:
            parser.error("key requires a value (e.g. W, SPACE, ENTER)")
        result = call("POST", "/key", {"key": args.value, "hold_ms": args.hold, "method": args.method}, base=args.base)
    elif args.action == "text":
        if not args.value:
            parser.error("text requires a value")
        result = call("POST", "/text", {"text": args.value, "method": args.method}, base=args.base)
    elif args.action == "command":
        if not args.value:
            parser.error("command requires a value (e.g. /reloadui)")
        result = call(
            "POST",
            "/command",
            {"command": args.value, "open_chat": not args.no_chat, "method": args.method},
            base=args.base,
        )
    elif args.action == "screenshot":
        result = call("GET", "/screenshot", base=args.base)
        if result.get("ok") and "data" in result:
            import os

            out_path = os.path.join(os.path.dirname(__file__), "rift-screenshot.bmp")
            with open(out_path, "wb") as f:
                f.write(__import__("base64").b64decode(result["data"]))
            result["saved_to"] = out_path
    elif args.action == "memory":
        if not args.value:
            parser.error("memory requires an address (e.g. 0x7FF600001000)")
        result = call("POST", "/memory", {"address": args.value, "size": args.size}, base=args.base)
    else:
        parser.error(f"unknown action {args.action}")

    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
