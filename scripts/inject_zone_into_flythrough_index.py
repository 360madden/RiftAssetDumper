"""Inject per-asset zone field into flythrough-index.json.

Reads:
  - Exports/semantic-phase1/fly_asset_zone_map_v2.json (per-asset zone map)
  - Assets/build/flythrough/flythrough-index.json (source of truth, 229 assets)

Writes:
  - Assets/build/flythrough/flythrough-index.json (in-place: each asset gains
    a `zone` sub-record with tuple/expansion/category/name/method/delta)
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FLY_INDEX = REPO_ROOT / "Assets" / "build" / "flythrough" / "flythrough-index.json"
ZONE_MAP = REPO_ROOT / "Exports" / "semantic-phase1" / "fly_asset_zone_map_v2.json"


def main() -> int:
    with open(ZONE_MAP, encoding="utf-8-sig") as f:
        zm = json.load(f)
    zone_map = zm["fly_asset_zone_map"]
    print(f"[1] loaded zone map: {len(zone_map)} entries")

    with open(FLY_INDEX, encoding="utf-8-sig") as f:
        fly = json.load(f)
    n_assets = len(fly["assets"])
    print(f"[2] flythrough-index.json: {n_assets} assets")

    missing = []
    for aid, asset in fly["assets"].items():
        z = zone_map.get(aid)
        if z is None:
            missing.append(aid)
            asset["zone"] = {
                "tuple": None,
                "expansion": None,
                "category": None,
                "name": None,
                "method": "unmatched",
                "delta": None,
                "first4": "",
                "confidence": None,
            }
        else:
            asset["zone"] = {
                "tuple": z.get("tuple"),
                "expansion": z.get("expansion"),
                "category": z.get("category"),
                "name": z.get("name"),
                "method": z.get("method", "unmatched"),
                "delta": z.get("delta"),
                "first4": z.get("first4", ""),
                "confidence": z.get("confidence"),
            }
    print(f"[3] injected zone into {n_assets} assets; {len(missing)} missing in map (set to unmatched)")

    FLY_INDEX.write_text(
        json.dumps(fly, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"[4] wrote {FLY_INDEX.relative_to(REPO_ROOT)} ({FLY_INDEX.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
