import json
import time
import urllib.request

keys = ["W", "S", "Q", "E"]
url = "http://localhost:8769/key"

for key in keys:
    payload = json.dumps({"key": key, "hold_ms": 1000, "method": "post"}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode()
        print(f"{key}: {body}")
    time.sleep(1)
