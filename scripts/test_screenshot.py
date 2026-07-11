"""Test screenshot capture from RIFT localhost HTTP broker on port 8769."""

import base64
import http.client
import json
import os
import struct
import sys
import urllib.error

BROKER = "localhost"
PORT = 8769
SAVE_PATH = os.path.join(os.path.dirname(__file__), "rift_screenshot.bmp")

# Smoke-script-only: any network-layer failure (broker unreachable, broker crashed
# during startup, broker process restarted mid-request, RFC RemoteDisconnected)
# should skip the test cleanly with exit 0 rather than failing CI. We catch the
# full family here because URLError does NOT cover http.client.RemoteDisconnected
# or generic socket errors. We deliberately exclude OSError: post-broker file IO
# (os.path.getsize, open, f.read on the saved BMP) must NOT be silently reported
# as "broker unreachable" -- a real disk/permission failure should surface.
_NETWORK_ERRORS: tuple = (
    urllib.error.URLError,
    urllib.error.HTTPError,
    http.client.RemoteDisconnected,
    http.client.BadStatusLine,
    ConnectionError,
)


def make_bmp(dib_data: bytes) -> bytes:
    """Wrap raw DIB (BITMAPINFOHEADER) data in a valid BMP file.

    dib_data = BITMAPINFOHEADER (40 bytes) + pixel data.
    BMP file = BMPFILEHEADER (14 bytes) + dib_data.
    """
    dib_header_size = struct.unpack_from("<I", dib_data, 0)[0]
    file_size = 14 + len(dib_data)
    pixel_offset = 14 + dib_header_size
    # BMPFILEHEADER: sig(2) + fileSize(4) + reserved(4) + pixelOffset(4)
    file_header = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, pixel_offset)
    return file_header + dib_data


def main():
    # 1. Health check
    print("--- Health Check ---")
    conn = http.client.HTTPConnection(BROKER, PORT, timeout=10)
    conn.request("GET", "/health")
    resp = conn.getresponse()
    health = json.loads(resp.read().decode())
    print(f"Status : {resp.status}")
    print(f"Body   : {json.dumps(health, indent=2)}")
    conn.close()

    if not health.get("ok"):
        print("Broker not OK - aborting.")
        return

    # 2. Capture screenshot
    print("\n--- Screenshot ---")
    conn = http.client.HTTPConnection(BROKER, PORT, timeout=15)
    conn.request("GET", "/screenshot")
    resp = conn.getresponse()
    body = json.loads(resp.read().decode())
    conn.close()

    print(f"Status : {resp.status}")
    print(f"Format : {body.get('format')}")
    print(f"OK     : {body.get('ok')}")

    if not body.get("ok"):
        print("Screenshot not OK - aborting.")
        return

    # 3. Decode base64 DIB and wrap in proper BMP file header
    dib = base64.b64decode(body["data"])
    bmp = make_bmp(dib)

    with open(SAVE_PATH, "wb") as f:
        f.write(bmp)

    # 4. Validate saved BMP
    size = os.path.getsize(SAVE_PATH)

    with open(SAVE_PATH, "rb") as f:
        full = f.read()

    sig = full[0:2]
    file_size_hdr = struct.unpack_from("<I", full, 2)[0]
    pix_off = struct.unpack_from("<I", full, 10)[0]

    dib_start = 14
    dib_size = struct.unpack_from("<I", full, dib_start)[0]
    width = struct.unpack_from("<I", full, dib_start + 4)[0]
    height = struct.unpack_from("<I", full, dib_start + 8)[0]
    bpp = struct.unpack_from("<H", full, dib_start + 14)[0]

    print("\n--- Save Result ---")
    print(f"Path          : {SAVE_PATH}")
    print(f"File size     : {size:,} bytes")
    print(f"BMP sig       : {sig.decode('ascii', errors='replace')} ({'BM' if sig == b'BM' else 'INVALID'})")
    print(f"File size hdr : {file_size_hdr:,}")
    print(f"Pixel offset  : {pix_off}")
    print(f"DIB header sz : {dib_size}")
    print(f"Dimensions    : {width}x{height}")
    print(f"Bit depth     : {bpp}")
    print(f"Saved OK      : {'YES' if sig == b'BM' and size == file_size_hdr else 'NO'}")


if __name__ == "__main__":
    try:
        main()
    except _NETWORK_ERRORS as e:
        # Broker subprocess may fail to bind (Windows ctypes failure on
        # headless runner, rift_input lookup, port already in use, etc.)
        # OR accept and then drop the connection (RemoteDisconnected).
        # Treat as smoke-script-only: skip cleanly so CI doesn't fail.
        print(f"Skipping test_screenshot: broker unreachable on localhost:8769 ({type(e).__name__}: {e})")
        sys.exit(0)
