"""Batch scene graph probe for FT-4 pipeline.

Runs probe-nif-scene-graph against NIF hashes from merged.obj and
aggregates NiNode transform data into per-asset manifest files.
"""

import json
import subprocess
import time
from pathlib import Path

LIVE_ROOT = "C:/Program Files (x86)/Glyph/Games/RIFT/Live"
DOTNET_PROJ = "src/RiftAssetDumper/RiftAssetDumper.csproj"
MERGED_OBJ = "../RiftFlythrough/merged.obj"
OUT_DIR = Path("../RiftFlythrough/objs")


def extract_hashes(obj_path, limit=None):
    hashes = set()
    with open(obj_path) as f:
        for line in f:
            if line.startswith("o "):
                h = line[2:].strip().replace("ptonly_", "")
                if len(h) == 16 and all(c in "0123456789abcdef" for c in h):
                    hashes.add(h)
                    if limit and len(hashes) >= limit:
                        break
    return sorted(hashes)


def probe_scene_graph(nif_hash):
    sg_path = Path(LIVE_ROOT) / "Exports" / "nif-scene-graph.json"
    # Remove old output file to detect new writes
    if sg_path.exists():
        sg_path.unlink()
    cmd = [
        "dotnet",
        "run",
        "--project",
        DOTNET_PROJ,
        "--",
        "probe-nif-scene-graph",
        "--id",
        nif_hash,
        "--root",
        LIVE_ROOT,
        "--no-redact-paths",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    # Wait for file to appear
    for _ in range(30):
        if sg_path.exists() and sg_path.stat().st_size > 0:
            break
        time.sleep(0.2)
    if sg_path.exists() and sg_path.stat().st_size > 0:
        return json.loads(sg_path.read_text()), r.stderr
    return None, r.stderr


def main():
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=0, help="Max hashes to probe")
    p.add_argument("--out", default=str(OUT_DIR), help="Output dir for manifests")
    args = p.parse_args()

    hashes = extract_hashes(MERGED_OBJ, args.limit or None)
    print(f"Found {len(hashes)} unique NIF hashes")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for i, h in enumerate(hashes):
        print(f"[{i + 1}/{len(hashes)}] {h}...", end=" ", flush=True)
        t0 = time.time()
        sg, stderr = probe_scene_graph(h)
        elapsed = time.time() - t0

        if sg:
            ni_nodes = [b for b in sg.get("NiNodes", [])]
            if ni_nodes:
                node = ni_nodes[0]
                manifest = {
                    "SchemaVersion": "asset-mesh-manifest/v1",
                    "nif_hash": h,
                    "transform": {
                        "translation": node.get("Translation", [0, 0, 0]),
                        "rotation": node.get("Rotation", [1, 0, 0, 0]),
                        "scale": node.get("Scale", 1.0),
                    },
                }
                mf_path = out_dir / f"{h}.obj.manifest.json"
                mf_path.write_text(json.dumps(manifest, indent=2))
                results.append({"hash": h, "transform": manifest["transform"], "elapsed": round(elapsed, 2)})
                print(f"OK ({elapsed:.1f}s)")
            else:
                print("no NiNodes")
        else:
            print("FAIL" if "ERROR" in stderr else "no data")

    # Write summary
    summary = {"total": len(hashes), "success": len(results), "manifests": results}
    (out_dir / "scene-graph-summary.json").write_text(json.dumps(summary, indent=2))
    print(f"Done: {len(results)}/{len(hashes)} successful")


if __name__ == "__main__":
    main()
