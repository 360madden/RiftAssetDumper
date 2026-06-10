"""Infer missing mesh_sizes from existing probe-meshsize-lookup patterns.

Strategy: For each asset missing mesh_size, find the closest match in the probe lookup
based on (vertex_count, face_count, descriptor) similarity. Uses:
1. Exact (VC, FC) match in probe lookup -> direct assignment
2. Closest VC match
3. Cross-reference with sibling_pair mesh_size for pos-only assets
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORT_MANIFEST = REPO_ROOT / "Exports" / "export-manifest.json"
PROBE_LOOKUP = REPO_ROOT / "Exports" / "probe-meshsize-lookup.json"


def _load_json(path: Path, encoding: str = "utf-8") -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, encoding=encoding) as f:
        return json.load(f)


def load_known_mappings() -> dict[tuple[int, int], int]:
    """Build (vertex_count, face_count) -> mesh_size mapping from probe lookup."""
    em = _load_json(EXPORT_MANIFEST)
    pl = _load_json(PROBE_LOOKUP)

    aid_info: dict[str, tuple[int, int, str, bool]] = {}
    for e in em.get("entries", []):
        aid = e.get("asset_id", "")
        if aid and len(aid) == 16:
            aid_info[aid] = (
                e.get("vertex_count", 0),
                e.get("face_count", 0),
                e.get("descriptor", ""),
                e.get("faced", False),
            )

    mapping: dict[tuple[int, int], int] = {}
    conflicts: dict[tuple[int, int], set[int]] = {}
    for aid, pinfo in pl.get("entries", {}).items():
        ms = pinfo.get("meshsize")
        if ms and aid in aid_info:
            vc, fc, _, _ = aid_info[aid]
            key = (vc, fc)
            if key in mapping and mapping[key] != ms:
                conflicts.setdefault(key, {mapping[key]}).add(ms)
            mapping[key] = ms
    if conflicts:
        for key, mss in conflicts.items():
            print(f"  NOTE: (VC={key[0]}, FC={key[1]}) has conflicting mesh_sizes: {sorted(mss)}")
    return mapping


def infer_meshsize(
    vc: int,
    fc: int,
    desc: str,
    sibling_ms: int | None,
    known: dict[tuple[int, int], int],
) -> int | None:
    """Infer mesh_size for an asset given its attributes."""
    if vc == 0:
        return None

    # 1. Exact (VC, FC) match
    if (vc, fc) in known:
        return known[(vc, fc)]

    # 2. Match by vertex_count
    same_vc = {(v, f): ms for (v, f), ms in known.items() if v == vc}
    if same_vc:
        from collections import Counter

        return Counter(same_vc.values()).most_common(1)[0][0]

    # 3. Closest vertex_count (within 20% or 10 absolute)
    candidates = sorted(known.items(), key=lambda x: abs(x[0][0] - vc))
    if candidates:
        closest_vc = candidates[0][0][0]
        if abs(closest_vc - vc) <= max(10, vc * 0.2):
            return candidates[0][1]

    # 4. Sibling_pair fallback
    if sibling_ms:
        return sibling_ms

    return None


def main() -> None:
    print("Inferring missing mesh_sizes...")

    em = _load_json(EXPORT_MANIFEST)
    pl = _load_json(PROBE_LOOKUP)

    known = load_known_mappings()
    print(f"Known (VC,FC) -> mesh_size patterns: {len(known)}")

    # Build aid info and sibling lookup
    aid_info: dict[str, dict[str, Any]] = {}
    aid_to_sibling_ms: dict[str, int | None] = {}
    for e in em.get("entries", []):
        aid = e.get("asset_id", "")
        if aid and len(aid) == 16:
            aid_info[aid] = {
                "vc": e.get("vertex_count", 0),
                "fc": e.get("face_count", 0),
                "desc": e.get("descriptor", ""),
                "faced": e.get("faced", False),
            }
            sp = e.get("sibling_pair")
            if isinstance(sp, dict) and sp.get("mesh_size"):
                aid_to_sibling_ms[aid] = sp["mesh_size"]

    probe_aids = set(pl.get("entries", {}).keys())

    inferred: dict[str, int] = {}
    confidence: dict[str, str] = {}

    for aid, info in aid_info.items():
        if aid in probe_aids:
            continue

        sibling_ms = aid_to_sibling_ms.get(aid)
        ms = infer_meshsize(
            info["vc"],
            info["fc"],
            info["desc"],
            sibling_ms,
            known,
        )

        if ms is not None:
            if (info["vc"], info["fc"]) in known:
                conf = "exact_match"
            elif sibling_ms and ms == sibling_ms:
                conf = "sibling_pair"
            else:
                conf = "vc_proximity"
            inferred[aid] = ms
            confidence[aid] = conf

    print(f"Inferred mesh_sizes: {len(inferred)}")

    # Update probe lookup
    for aid, ms in inferred.items():
        pl.setdefault("entries", {})[aid] = {
            "meshsize": ms,
            "mesh_block": 6,
            "faced": aid_info[aid]["faced"],
            "note": f"inferred via {confidence[aid]} (vc={aid_info[aid]['vc']}, fc={aid_info[aid]['fc']})",
        }

    # Write enriched lookup (new file only, don't overwrite original)
    out_path = PROBE_LOOKUP.parent / "probe-meshsize-lookup-enriched.json"
    pl["description"] = pl.get("description", "") + " + inferred mesh_sizes for unprobed assets"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(pl, f, indent=2, default=str)
    print(f"Written enriched lookup: {out_path} ({out_path.stat().st_size} bytes)")

    # Stats
    exact = sum(1 for c in confidence.values() if c == "exact_match")
    prox = sum(1 for c in confidence.values() if c == "vc_proximity")
    sib = sum(1 for c in confidence.values() if c == "sibling_pair")
    print(f"Confidence: {exact} exact, {prox} proximity, {sib} sibling")
    remaining = len(aid_info) - len(probe_aids) - len(inferred)
    print(f"Still unclassified: {remaining}")


if __name__ == "__main__":
    main()
