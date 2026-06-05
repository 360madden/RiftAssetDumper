import os
import shutil
import sys

src_root = sys.argv[1] if len(sys.argv) > 1 else "Exports/extracted-top260"
dst_root = sys.argv[2] if len(sys.argv) > 2 else "Exports/live-nifs"

os.makedirs(dst_root, exist_ok=True)
copied = 0

for dirpath, _, filenames in os.walk(src_root):
    for f in filenames:
        if f.endswith(".nif"):
            src = os.path.join(dirpath, f)
            # Extract bundle ID from path
            parts = dirpath.replace(os.sep, "/").split("/")
            bundle_id = parts[-2] if len(parts) >= 2 else "unknown"
            dst = os.path.join(dst_root, f"{bundle_id}.nif")
            if not os.path.exists(dst):
                shutil.copy2(src, dst)
                copied += 1

print(f"Copied {copied} NIF files to {dst_root}")
