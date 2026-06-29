"""Build per-asset zone map from zone-full.json.

Re-derives a per-fly-asset zone attribution from the hint:map-zone scan output
(zone-full.json), with archive-neighbor fallback for assets lacking the
source-path metadata. Writes fly_asset_zone_map_v2.json with the nested
zone sub-record ready for injection into flythrough-index.json.

Output schema (per asset):
  {
    "tuple": "vanilla.world_objects.props" | null,
    "expansion": "vanilla" | "ep1" | "ep2" | "ep3" | null,
    "category": "world_objects" | ... | null,
    "name": "props" | ... | null,
    "method": "direct" | "neighbor" | "unmatched",
    "delta": 0 | <int> | null  # entry-index distance (0 for direct match)
  }
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import ijson

REPO_ROOT = Path(__file__).resolve().parents[1]
FLY_INDEX = REPO_ROOT / "Assets" / "build" / "flythrough" / "flythrough-index.json"
LAI = REPO_ROOT / "Exports" / "discovery-plan" / "live-nif-archive-index.json"
ZONE_FULL = REPO_ROOT / "Exports" / "semantic-phase1" / "zone-full.json"
OUT = REPO_ROOT / "Exports" / "semantic-phase1" / "fly_asset_zone_map_v2.json"

EXPANSIONS = {"vanilla", "ep1", "ep2", "ep3"}
NEIGHBOR_WINDOW = 150

# Cycle 5.2: standard Gamebryo NIF magic ("Game" = 0x47616d65). Recorded for
# transparency only -- see docs/handoffs/2026-06-28-archive-neighbor-verification.md
# for why First4 alone does NOT discriminate siblings from coincidental neighbors.
EXPECTED_FIRST4 = "47616d65"


def derive_confidence(method: str, delta: int | None) -> str | None:
    # Map (method, |delta|) to a confidence bucket.
    # Buckets (calibrated against the archive-neighbor verification handoff):
    #   high:   direct match (delta=0) OR tight co-bundled sibling (|delta| <= 5)
    #   medium: plausible sibling (6 <= |delta| <= 30)
    #   low:    coincidental adjacency (|delta| > 30)
    #   None:   unmatched (no attribution)
    # Thresholds mirror the verification handoff empirical findings:
    #   15/65 (23%) at |delta| <= 5 -> high
    #   27/65 (42%) at 6 <= |delta| <= 30 -> medium (may include some coincidental)
    #   23/65 (35%) at |delta| > 30 -> low (confirmed-suspicious)
    if method == "unmatched" or delta is None:
        return None
    d = abs(delta)
    if method == "direct" or d <= 5:
        return "high"
    if d <= 30:
        return "medium"
    return "low"


def extract_z_path(snippet: str) -> str:
    """Strip any 'NIF Creation Information >> ' prefix and return 'Z:/TWN/...'.

    zone-full snippets come in two shapes:
      - "Z:/TWN/art/project/..."                (clean path)
      - "NIF Creation Information >> Z:/TWN/..." (prefixed)
    Both must yield the same parsed result.
    """
    if not snippet:
        return ""
    idx = snippet.find("Z:/TWN/")
    if idx < 0:
        return ""
    return snippet[idx:]


def parse_path(snippet: str) -> dict | None:
    """Parse 'Z:/TWN/art/project/<expansion?>/<category>/<zone>/...' into the
    nested zone sub-record. Returns None when the path is unparseable.
    """
    z = extract_z_path(snippet)
    if not z:
        return None
    s = z.replace("\\", "/").lower()
    prefix = "z:/twn/art/project/"
    if not s.startswith(prefix):
        return None
    parts = s[len(prefix) :].split("/")
    if len(parts) < 2:
        return None
    if parts[0] in EXPANSIONS:
        if len(parts) < 3:
            return None
        exp, cat, zone = parts[0], parts[1], parts[2]
    else:
        exp, cat, zone = "vanilla", parts[0], parts[1]
    return {
        "expansion": exp,
        "category": cat,
        "name": zone,
        "tuple": f"{exp}.{cat}.{zone}",
    }


def main() -> int:
    with open(FLY_INDEX, encoding="utf-8-sig") as f:
        fly = json.load(f)
    fly_ids = set(fly["assets"].keys())
    print(f"[1] fly IDs: {len(fly_ids)}")

    with open(LAI, encoding="utf-8-sig") as f:
        lai = json.load(f)
    id_to_arch_ei: dict[str, tuple[str, int]] = {}
    for r in lai:
        nid = (r.get("NifHash", "") or "").lower()
        if nid:
            id_to_arch_ei[nid] = (r.get("ArchiveName", "?"), int(r.get("EntryIndex", -1)))
    print(f"[2] live-nif-archive-index rows: {len(lai)}")

    # First4 is recorded per-entry for transparency (see EXPECTED_FIRST4
    # rationale). The tuple now carries (ei, parsed, z_path, first4) so the
    # neighbor-resolution pass can surface the magic of the chosen neighbor.
    arc_entries: dict[str, list[tuple[int, dict | None, str, str]]] = defaultdict(list)
    direct_matches: dict[str, dict] = {}
    with open(ZONE_FULL, encoding="utf-8-sig") as f:
        for e in ijson.items(f, "Entries.item"):
            arc = e.get("ArchiveName", "?")
            ei = int(e.get("EntryIndex", -1))
            snippets = e.get("TextSnippetSamples", []) or []
            z_path = next((s for s in snippets if "Z:/TWN/" in (s or "")), "")
            parsed = parse_path(z_path) if z_path else None
            first4 = (e.get("First4", "") or "").lower()
            arc_entries[arc].append((ei, parsed, z_path, first4))
            aid = (e.get("AssetIdPrefix", "") or "").lower()
            if aid in fly_ids and parsed is not None:
                direct_matches[aid] = (parsed, first4)
    print(f"[3] direct matches (fly ID in zone-full with parseable path): {len(direct_matches)}")

    fly_zone_map: dict[str, dict] = {}
    for aid, (p, first4) in direct_matches.items():
        # First4 is recorded for transparency (see EXPECTED_FIRST4 rationale);
        # for direct matches it is the First4 of the matching zone-full entry.
        fly_zone_map[aid] = {
            **p,
            "method": "direct",
            "delta": 0,
            "first4": first4,
            "confidence": derive_confidence("direct", 0),
        }

    unmatched_after_direct = fly_ids - set(fly_zone_map.keys())
    print(f"[4] unmatched after direct: {len(unmatched_after_direct)}")
    resolved_via_neighbor = 0
    for aid in unmatched_after_direct:
        arc, target_ei = id_to_arch_ei.get(aid, ("?", -1))
        if arc == "?" or arc not in arc_entries:
            continue
        best_parsed: dict | None = None
        best_d: int | None = None
        best_first4: str = ""
        for ei, parsed, _, first4 in arc_entries[arc]:
            if parsed is None:
                continue
            d = abs(ei - target_ei)
            if d > NEIGHBOR_WINDOW:
                continue
            if best_d is None or d < best_d:
                best_parsed = parsed
                best_d = d
                best_first4 = first4
        if best_parsed is not None and best_d is not None:
            fly_zone_map[aid] = {
                **best_parsed,
                "method": "neighbor",
                "delta": best_d,
                "first4": best_first4,
                "confidence": derive_confidence("neighbor", best_d),
            }
            resolved_via_neighbor += 1
    print(f"[5] resolved via archive-neighbor (+/-{NEIGHBOR_WINDOW}): {resolved_via_neighbor}")

    for aid in fly_ids:
        if aid not in fly_zone_map:
            fly_zone_map[aid] = {
                "tuple": None,
                "expansion": None,
                "category": None,
                "name": None,
                "method": "unmatched",
                "delta": None,
                "first4": "",
                "confidence": None,
            }

    method_dist = Counter(z["method"] for z in fly_zone_map.values())
    tuple_dist = Counter(z["tuple"] for z in fly_zone_map.values() if z["tuple"])
    confidence_dist = Counter(z.get("confidence") for z in fly_zone_map.values())
    print(f"[6] total: {len(fly_zone_map)}; method: {dict(method_dist)}")
    print(f"    confidence: {dict(confidence_dist)}")
    print("    top 10 zones:")
    for t, ct in tuple_dist.most_common(10):
        print(f"      {t}: {ct}")

    out = {
        "fly_asset_zone_map": fly_zone_map,
        "method_distribution": dict(method_dist),
        "confidence_distribution": {str(k): v for k, v in confidence_dist.items()},
        "neighbor_window": NEIGHBOR_WINDOW,
        "expected_first4": EXPECTED_FIRST4,
        "first4_discriminates": False,
        "first4_rationale": (
            "First4 magic does NOT discriminate siblings from coincidental "
            "neighbors; the archive-neighbor verification handoff (2026-06-28) "
            "found all 5 closest and all 3 farthest neighbors share First4 "
            f"{EXPECTED_FIRST4}. Entry-Index Delta is the discriminating signal. "
            "First4 is recorded for transparency only."
        ),
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"[7] saved {OUT.relative_to(REPO_ROOT)} ({len(fly_zone_map)} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
