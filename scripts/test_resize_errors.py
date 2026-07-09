"""Test resize error cases."""

import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    # Start broker
    p = subprocess.Popen(
        [sys.executable, os.path.join(os.path.dirname(__file__), "rift_broker.py"), "--port", "8769"],
        creationflags=0x00000008 | 0x00000200,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3)

    # Verify
    resp = urllib.request.urlopen("http://localhost:8769/health").read().decode()
    print("Health:", resp)

    # Test error cases
    print("\nError cases:")
    for size in ["500x300", "2560x1440", "800x600", "garbage", "640x360"]:
        data = json.dumps({"size": size}).encode()
        req = urllib.request.Request(
            "http://localhost:8769/resize",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        result = json.loads(urllib.request.urlopen(req).read().decode())
        if result["ok"]:
            after = result["after"]["client"]
            print(f"  {size:>10} -> OK: {after}")
        else:
            err = result.get("error", "unknown")
            print(f"  {size:>10} -> ERROR: {err}")

    p.terminate()
    print("\nDone.")


if __name__ == "__main__":
    main()
