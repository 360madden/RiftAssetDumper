#!/usr/bin/env python3
"""
grok-here.py

Convenient Python launcher for Grok in the RiftAssetDumper repo.

Enforces memory (cross-session recall) and provides a single command
to start well-configured sessions from this directory.

Usage:
    python grok-here.py
    python grok-here.py --prompt "Continue the position source work"
    python grok-here.py --yolo
"""

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).parent.resolve()
    os.chdir(repo_root)

    # Defense-in-depth: ensure memory is enabled for this workspace
    os.environ.setdefault("GROK_MEMORY", "1")

    # Parse very simple flags so we can forward them nicely
    args = sys.argv[1:]
    grok_args = ["grok"]

    prompt = None
    yolo = False
    model = "grok-build"

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--prompt", "-p"):
            if i + 1 < len(args):
                prompt = args[i + 1]
                i += 1
        elif arg == "--yolo":
            yolo = True
        elif arg in ("--model", "-m") and i + 1 < len(args):
            model = args[i + 1]
            i += 1
        else:
            # Pass everything else through
            grok_args.append(arg)
        i += 1

    if prompt:
        grok_args.extend(["--prompt", prompt])
    if yolo:
        grok_args.append("--yolo")
    if model:
        grok_args.extend(["--model", model])

    print("Starting Grok in RiftAssetDumper (memory enabled)...")
    print(f"Working directory: {repo_root}")
    print("Use /memory, /flush, /dream, and 'remember ...' inside the session.")
    print()

    try:
        result = subprocess.run(grok_args)
        sys.exit(result.returncode)
    except FileNotFoundError:
        print("Error: 'grok' command not found in PATH.", file=sys.stderr)
        print("Make sure the Grok CLI is installed and on your PATH.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
