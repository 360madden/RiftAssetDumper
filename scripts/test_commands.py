import json
import time
import urllib.request

URL = "http://localhost:8769/command"

commands = [
    {"command": "/wave", "open_chat": True},
    {"command": "/dance", "open_chat": True},
]

for i, cmd in enumerate(commands):
    if i > 0:
        time.sleep(2)
    data = json.dumps(cmd).encode("utf-8")
    req = urllib.request.Request(URL, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            print(json.dumps(body, indent=2))
    except Exception as e:
        print(f"Error sending {cmd['command']}: {e}")
