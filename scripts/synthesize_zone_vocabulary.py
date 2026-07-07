"""
Synthesize a compact zone vocabulary from a ``build-asset-semantic-index`` JSON
output file (schema ``asset-semantic-index/v1``).

Filters to entries tagged ``hint:map-zone``, classifies extracted strings into
semantic buckets (zone names, map keys, shader references, file paths, other),
and groups entries by shared ``TextSnippetSamples`` values.

Usage:
    python scripts/synthesize_zone_vocabulary.py
    python scripts/synthesize_zone_vocabulary.py <input> [<output>]

Defaults:
    input  = Exports/semantic-phase1/zone-50k.json
    output = Exports/semantic-phase1/zone-vocabulary.json
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

SHADER_KEYWORDS: frozenset[str] = frozenset(
    {
        "worldInverse",
        "worldView",
        "worldTranspose",
        "worldInverseTranspose",
        "viewMatrix",
        "projectionMatrix",
        "modelMatrix",
        "normalMatrix",
        "worldMatrix",
        "boneMatrix",
        "lightPosition",
        "eyePosition",
        "vertexPosition",
        "texCoordOffset",
        "fogParams",
        "materialAmbient",
        "materialDiffuse",
        "boneQuat",
        "boneTranslate",
        "boneScale",
        "texCoord",
        "diffuseColor",
        "specularColor",
        "alphaRef",
        "clipPlane",
        "depthBias",
        "SkinningPalette",
        "ViewVector",
    }
)

DEFAULT_INPUT = Path("Exports/semantic-phase1/zone-50k.json")
DEFAULT_OUTPUT = Path("Exports/semantic-phase1/zone-vocabulary.json")


def classify_string(s: str) -> str:
    if not isinstance(s, str) or not s:
        return "other"
    if "\\" in s or "/" in s:
        return "file_paths"
    if "." in s:
        return "file_paths"
    s_lower = s.lower()
    for kw in SHADER_KEYWORDS:
        if kw.lower() in s_lower:
            return "shader_references"
    if "_" in s and not s[0].isupper():
        return "map_keys"
    if s[0].isupper():
        return "zone_names"
    return "other"


def collect_strings(entry: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for field in ("NameCandidates", "TextSnippetSamples", "ReferenceSamples"):
        for s in entry.get(field) or []:
            if isinstance(s, str) and s and s not in seen:
                seen.add(s)
                out.append(s)
    return out


def build_zone_vocabulary(
    entries: list[dict[str, Any]],
    inspected_payloads: int = 0,
    source_name: str = "",
) -> dict[str, Any]:
    zone_entries: list[dict[str, Any]] = []
    for entry in entries:
        cats = entry.get("SemanticCategories") or []
        if not isinstance(cats, list):
            continue
        if "hint:map-zone" not in cats:
            continue
        zone_entries.append(entry)

    total_zone = len(zone_entries)

    all_unique: set[str] = set()
    entry_records: list[dict[str, Any]] = []

    for entry in zone_entries:
        aid = str(entry.get("AssetIdPrefix", "") or "")
        archive = str(entry.get("ArchiveName", "") or "")
        ei = entry.get("EntryIndex")
        if not isinstance(ei, int):
            ei = 0
        dtype = str(entry.get("DetectedType", "") or "")
        cats = list(entry.get("SemanticCategories") or [])

        strings = collect_strings(entry)
        classified: dict[str, list[str]] = {
            "zone_names": [],
            "map_keys": [],
            "shader_references": [],
            "file_paths": [],
            "other": [],
        }
        for s in strings:
            all_unique.add(s)
            cat = classify_string(s)
            classified[cat].append(s)

        entry_records.append(
            {
                "asset_id": aid,
                "archive": archive,
                "entry_index": ei,
                "type": dtype,
                "categories": cats,
                "text_snippet_samples": list(entry.get("TextSnippetSamples") or []),
                "classified": classified,
                "all_strings": strings,
            }
        )

    groups: dict[str, dict[str, Any]] = {}
    for rec in entry_records:
        samples = rec["text_snippet_samples"]
        if not samples:
            key = "@ungrouped"
            if key not in groups:
                groups[key] = _new_group(key)
            _add_to_group(groups[key], rec)
        else:
            for sample in samples:
                if sample not in groups:
                    groups[sample] = _new_group(sample)
                _add_to_group(groups[sample], rec)

    group_list = []
    for gk in sorted(groups):
        g = groups[gk]
        g["entries"] = sorted(g["entries"], key=lambda e: e["asset_id"])
        g["entry_count"] = len(g["entries"])
        g["zone_names"] = sorted(set(g["zone_names"]))
        g["map_keys"] = sorted(set(g["map_keys"]))
        g["file_paths"] = sorted(set(g["file_paths"]))
        g["shader_references"] = sorted(set(g["shader_references"]))
        group_list.append(g)

    all_sorted = sorted(all_unique)
    classified_all: dict[str, list[str]] = {
        "zone_names": [],
        "map_keys": [],
        "shader_references": [],
        "file_paths": [],
        "other": [],
    }
    for s in all_sorted:
        classified_all[classify_string(s)].append(s)

    return {
        "schema": "zone-vocabulary-v1",
        "generated_at": str(date.today()),
        "source_inventory": source_name,
        "total_zone_entries": total_zone,
        "total_inspected_payloads": inspected_payloads,
        "classification_counts": {k: len(v) for k, v in classified_all.items()},
        "groups": group_list,
        "all_unique_strings": all_sorted,
    }


def _new_group(group_key: str) -> dict[str, Any]:
    return {
        "group_key": group_key,
        "entry_count": 0,
        "zone_names": [],
        "map_keys": [],
        "file_paths": [],
        "shader_references": [],
        "entries": [],
    }


def _add_to_group(group: dict[str, Any], rec: dict[str, Any]) -> None:
    group["zone_names"].extend(rec["classified"]["zone_names"])
    group["map_keys"].extend(rec["classified"]["map_keys"])
    group["file_paths"].extend(rec["classified"]["file_paths"])
    group["shader_references"].extend(rec["classified"]["shader_references"])
    group["entries"].append(
        {
            "asset_id": rec["asset_id"],
            "archive": rec["archive"],
            "entry_index": rec["entry_index"],
            "type": rec["type"],
        }
    )


def main(argv: list[str]) -> int:
    input_path = Path(argv[0]) if len(argv) > 0 else DEFAULT_INPUT
    output_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUTPUT

    print(f"Reading: {input_path}")
    data = json.loads(input_path.read_text(encoding="utf-8-sig"))

    entries = data.get("Entries")
    if not isinstance(entries, list):
        print(f"ERROR: input JSON has no 'Entries' list (got {type(entries).__name__})", file=sys.stderr)
        return 1

    source_name = str(input_path)
    inspected_payloads = data.get("InspectedPayloads", 0) or 0
    vocabulary = build_zone_vocabulary(entries, inspected_payloads=inspected_payloads, source_name=source_name)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(vocabulary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    total = vocabulary["total_zone_entries"]
    group_count = len(vocabulary["groups"])
    unique_strings = len(vocabulary["all_unique_strings"])
    print(f"Written: {output_path}")
    print(f"  zone entries:     {total}")
    print(f"  groups:           {group_count}")
    print(f"  unique strings:   {unique_strings}")
    if group_count:
        print(f"  largest group:    {max(g['entry_count'] for g in vocabulary['groups'])} entries")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
