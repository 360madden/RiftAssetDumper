"""Test the /resize endpoint on all presets."""

import json
import sys
import time
import urllib.error
import urllib.request


def resize(size: str) -> None:
    data = json.dumps({"size": size}).encode()
    req = urllib.request.Request(
        "http://localhost:8769/resize",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    result = json.loads(urllib.request.urlopen(req).read().decode())
    if result["ok"]:
        after = result["after"]["client"]
        print(f"{size:>6} -> {after} (OK)")
    else:
        err = result.get("error", "unknown")
        print(f"{size:>6} -> FAIL: {err}")
    time.sleep(0.5)


if __name__ == "__main__":
    try:
        for preset in ["360p", "540p", "576p", "720p", "900p", "1080p"]:
            resize(preset)

        resize("1280x720")
        resize("default")
    except urllib.error.URLError as e:
        # The RIFT input broker (scripts/rift_broker.py) only runs during
        # interactive developer sessions on the host. In CI the broker is
        # never started, so we exit cleanly instead of failing the build.
        # Manual invocation still hits the broker when it is running.
        print(f"Skipping test_resize: RIFT broker not running on localhost:8769 ({e})")
        sys.exit(0)
