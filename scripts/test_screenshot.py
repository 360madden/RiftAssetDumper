"""Test screenshot capture from RIFT localhost HTTP broker on port 8769."""

import base64
import http.client
import json
import os
import struct

BROKER = "localhost"
PORT = 8769
SAVE_PATH = os.path.join(os.path.dirname(__file__), "rift_screenshot.bmp")


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
    print(f"BMP sig       : {sig} ({'BM' if sig == b'BM' else 'INVALID'})")
    print(f"File size hdr : {file_size_hdr:,}")
    print(f"Pixel offset  : {pix_off}")
    print(f"DIB header sz : {dib_size}")
    print(f"Dimensions    : {width}x{height}")
    print(f"Bit depth     : {bpp}")
    print(f"Saved OK      : {'YES' if sig == b'BM' and size == file_size_hdr else 'NO'}")


if __name__ == "__main__":
    main()
