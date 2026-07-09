# RIFT Localhost Input Broker

A lightweight HTTP server that runs in your interactive session and executes input commands against the RIFT game window. The AI (or any local client) calls it via simple HTTP — no cross-session injection issues.

## Quick Start

1. **Start the broker** (in your interactive/elevated terminal):

   ```cmd
   scripts\start-rift-broker.cmd
   ```

2. **Call from AI or scripts**:

   ```bash
   python scripts/rift_broker_client.py health
   python scripts/rift_broker_client.py command "/reloadui"
   python scripts/rift_broker_client.py key W --hold 300
   python scripts/rift_broker_client.py text "hello"
   python scripts/rift_broker_client.py screenshot
   python scripts/rift_broker_client.py memory 0x7FF600001000 --size 64
   ```

3. **Or use curl**:

   ```bash
   curl http://127.0.0.1:8769/health
   curl -X POST http://127.0.0.1:8769/command -d '{"command":"/reloadui"}'
   curl http://127.0.0.1:8769/screenshot
   ```

## Endpoints

| Method | Path | Body | Description |
|--------|------|------|-------------|
| GET | `/health` | — | Check broker status, RIFT window info |
| GET | `/screenshot` | — | Capture window as BMP (base64 in response) |
| POST | `/resolve` | — | Re-resolve RIFT window (after game restart) |
| POST | `/key` | `{"key": "W", "hold_ms": 250, "method": "post"}` | Send a keystroke |
| POST | `/text` | `{"text": "hello", "method": "post"}` | Type text into focused element |
| POST | `/command` | `{"command": "/reloadui", "open_chat": true}` | Send chat command |
| POST | `/focus` | — | Acquire foreground focus |
| POST | `/restore` | — | Restore previous foreground window |
| POST | `/memory` | `{"address": "0x7FF600001000", "size": 64}` | Read process memory |

## Configuration

```cmd
scripts\start-rift-broker.cmd --port 8769 --process rift_x64 --method post
```

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | 8769 | HTTP server port |
| `--process` | rift_x64 | RIFT process name |
| `--pid` | — | Specific PID (if multiple instances) |
| `--method` | post | `post` (no-focus) or `sendinput` (foreground) |

## Logging

All commands are logged to `scripts/rift-broker.log` with timestamps:

```json
{"action": "command", "command": "/reloadui", "open_chat": true, "method": "post", "ts": "2026-07-08T11:51:46"}
```

## Reconnection

The client automatically checks `/health` and calls `/resolve` if RIFT restarted:

```python
from rift_broker_client import call
result = call("POST", "/command", {"command": "/reloadui"})
```

## Notes

- **PostMessage** (default) works for UI/chat/macro keys from any session.
- **SendInput** requires the broker to run in the same interactive session as RIFT (use `--method sendinput`).
- The broker is **localhost-only** (127.0.0.1) — no network exposure.
- **Screenshot** returns BMP format (base64-encoded). Use `--size` with memory reads.
- **Memory** reads require valid addresses in the target process (use `--size` to control read length).
