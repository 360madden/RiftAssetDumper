"""Test the /resize endpoint on all presets."""

import json
import time
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
    for preset in ["360p", "540p", "576p", "720p", "900p", "1080p"]:
        resize(preset)

    resize("1280x720")
    resize("default")
