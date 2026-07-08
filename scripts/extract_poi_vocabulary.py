#!/usr/bin/env python3
"""Extract POI entries from zone-50k.json and create a POI vocabulary.

Note: The hint:waypoint-poi category in the semantic index primarily contains
UI elements, asset references, and technical strings rather than actual
waypoint/location names. This script extracts what's available and documents
the limitation.
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INPUT = REPO_ROOT / "Exports" / "semantic-phase1" / "zone-50k.json"
OUTPUT = REPO_ROOT / "Exports" / "semantic-phase2" / "poi-vocabulary.json"

# Patterns to exclude (asset references, not POI names)
EXCLUDE_PATTERNS = [
    r"\.dds$",  # texture files
    r"\.png$",  # image files
    r"\.tga$",  # texture files
    r"\.nif$",  # model files
    r"^vfx_",  # VFX effects
    r"^fx_",  # effects
    r"^sp_",  # spell effects
    r"^C_S_",  # spawn effects
    r"^!",  # tooltip assets
    r"^\"",  # quoted asset names
    r"^#",  # hashed asset names
    r"^%",  # encoded asset names
    r"^&",  # encoded asset names
    r"^'",  # encoded asset names
    r"^\(",  # numbered items
    r"^--",  # comments
    r"^\.",  # hidden files
    r"^\d+[A-Z]",  # numbered effects
    r"<[a-z]",  # HTML/XML tags
    r"rdf:",  # RDF data
    r"xmlns:",  # XML namespaces
    r"Copyright",  # copyright notices
    r"NIF Creation",  # NIF metadata
    r"ExternalInterface",  # Flash/ActionScript
    r"HemiLight",  # lighting
    r"NiMesh",  # NiMesh
    r"NiSkinning",  # NiSkinning
    r"NiSource",  # NiSource
    r"OnFrame",  # Flash callbacks
    r"Quest",  # quest UI
    r"Respawn",  # respawn markers
    r"RiftTear",  # rift assets
    r"Button",  # button assets
    r"Window",  # window assets
    r"Tab_",  # tab assets
    r"RoundButton",  # round button assets
    r"StarFlare",  # star flare effects
    r"RingBlast",  # ring blast effects
    r"RingStar",  # ring star effects
    r"SnowFlake",  # snowflake effects
    r"RadialGlow",  # radial glow effects
    r"SoundManager",  # sound manager
    r"Transfer",  # transfer UI
    r"Upgradable",  # upgradable UI
    r"WorldEvent",  # world event UI
    r"Conquest",  # conquest UI
    r"Currency",  # currency UI
    r"POI_Tooltip",  # POI tooltip UI
    r"PORTRAIT",  # portrait UI
    r"PointLoc",  # point locations
    r"mc_contentFrame",  # Flash UI
    r"IconSlot",  # icon slots
    r"^Icon_",  # icons
    r"LifeRift",  # rift assets
    r"MainButton",  # button assets
    r"StrokeRelease",  # stroke effects
    r"WindowFrameCorner",  # window frame assets
]


def is_likely_poi(name: str) -> bool:
    """Check if a name looks like an actual POI (not an asset reference)."""
    if len(name) < 5:  # Minimum 5 chars for a POI name
        return False
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, name, re.IGNORECASE):
            return False
    # Must contain at least one letter
    if not re.search(r"[a-zA-Z]", name):
        return False
    # Exclude names that are just numbers + underscores
    if re.match(r"^[\d_]+$", name):
        return False
    # Exclude names with too many underscores (asset codes)
    if name.count("_") > 2:
        return False
    # Exclude names that look like asset hashes (hex strings)
    if re.match(r"^[0-9a-f]{8,}$", name.lower()):
        return False
    return True


with open(INPUT, encoding="utf-8-sig") as f:
    data = json.load(f)

entries = data.get("Entries", [])
poi_entries = [e for e in entries if "hint:waypoint-poi" in e.get("SemanticCategories", [])]

print(f"Total entries: {len(entries)}")
print(f"POI entries: {len(poi_entries)}")

# Extract POI names from text snippets and name candidates
poi_names = []
for e in poi_entries:
    snippets = e.get("TextSnippetSamples", [])
    names = e.get("NameCandidates", [])
    for s in snippets:
        if is_likely_poi(s):
            poi_names.append(s)
    for n in names:
        if is_likely_poi(n):
            poi_names.append(n)

# Deduplicate
unique_names = sorted(set(poi_names))
print(f"Unique POI names (filtered): {len(unique_names)}")

# Show first 30
for name in unique_names[:30]:
    print(f"  {name}")

# Create vocabulary
vocabulary = {
    "schema": "poi-vocabulary-v1",
    "generated_at": "2026-07-07",
    "source_file": "zone-50k.json",
    "total_poi_entries": len(poi_entries),
    "total_unique_names": len(unique_names),
    "names": unique_names,
    "entries": [],
}

# Add entry details
for e in poi_entries:
    vocabulary["entries"].append(
        {
            "archive": e.get("ArchiveName"),
            "entry_index": e.get("EntryIndex"),
            "type": e.get("DetectedType"),
            "name_candidates": e.get("NameCandidates", []),
            "text_snippets": e.get("TextSnippetSamples", []),
            "semantic_categories": e.get("SemanticCategories", []),
        }
    )

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(vocabulary, f, indent=2, ensure_ascii=False)

print(f"\nWrote {OUTPUT}")
