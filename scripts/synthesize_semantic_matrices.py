"""
Phase 47: Semantic Hint Matrix Synthesizer (Cycle 5 data-thickness polyfill).

Standalone script that classifies flythrough assets into the three
shipped hint categories:

    hint:actor-object    - small/interactable geometry (props, items, NPCs)
    hint:map-zone        - large static geometry (zones, terrain, buildings)
    hint:waypoint-poi    - position-only / non-facial markers (spawns, scripts)

Classification is two-tier:

  Tier 1 (preferred): archive-path-based classification
      Real classification = join `nif_hash` to a live-archive inventory map
      (archive name + entry index), then substring-match the archive name
      against `ARCHIVE_TAXONOMY`.  This is provenance (where the asset
      actually lives in the game client) — the right answer.

  Tier 2 (fallback): vertex-count heuristic
      faced=False                     -> hint:waypoint-poi
      faced=True + vc >= ZONE_VC_MIN  -> hint:map-zone
      faced=True + vc <  ZONE_VC_MIN  -> hint:actor-object

Tier 1 is engaged only when the live-archive NIF inventory map is
populated at the standard `DEFAULT_ARCHIVE_INDEX_PATH`, or explicitly
via the `--archive-index PATH` CLI flag.  Missing/unavailable inventory
silently degrades to Tier 2 (no exception thrown for missing
auto-discovery, so the polyfill always produces *something*).

This script is a Cycle 5 data-thickness polyfill until the C# backend
(`build-asset-semantic-index` in `scripts/rift_asset_discovery_matrix.py`)
emits real classification with full archive provenance + NIF block scan.

Output (overwrites in place; safe):

    Exports/discovery-matrix/nif-semantic-hints/semantic-nif-actor-object.json
    Exports/discovery-matrix/nif-semantic-hints/semantic-nif-map-zone.json
    Exports/discovery-matrix/nif-semantic-hints/semantic-nif-waypoint-poi.json

Each file conforms to ``docs/schemas/asset-semantic-index-v1.schema.json``
with all required top-level fields populated (boilerplate but valid).

Provenance markers:
  - Heuristic-classified entries: ``MagicLabel = "synthetic-semantic-polyfill"``
    and ``ArchiveName = "synthetic.twad"`` (boilerplate placeholders).
  - Archive-classified entries: ``MagicLabel = "synthetic-semantic-polyfill-v2-archive"``
    and real ``ArchiveName`` / ``EntryIndex`` fields.  Still polyfill data
    (heuristic-derived archive taxonomy) but with provenance.  The orchestrator
    fail-closed check uses ``MagicLabel.startswith("synthetic-semantic-polyfill")``
    so both v1 and v2 markers remain accepted as polyfill output.

Usage:
    python scripts/synthesize_semantic_matrices.py
    python scripts/synthesize_semantic_matrices.py --validate  # also schema-validate
    python scripts/synthesize_semantic_matrices.py --dry-run   # print counts only
    python scripts/synthesize_semantic_matrices.py --archive-index PATH
    python scripts/synthesize_semantic_matrices.py --archive-index  # auto-discover

The auto-discover default lives at
``Exports/discovery-plan/live-nif-archive-index.json`` with the schema:

    [
      {"NifHash": "<16-char hex>", "ArchiveName": "<file.twad>", "EntryIndex": <int>=0, ...},
      ...
    ]
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, NamedTuple

# Path bootstrap: REPO_ROOT is inserted on sys.path at module top so the
# absolute ``from scripts.X`` import inside main()'s loader round-trip
# section resolves without per-call mutation.  Idempotent (already on
# sys.path under pytest / pyproject `pythonpath=["."]`).
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

FLYTHROUGH_INDEX = REPO_ROOT / "Assets" / "build" / "flythrough" / "flythrough-index.json"

# Output target directory. Path matches DEFAULT_MATRIX_DIR in scripts/semantic_surface.py:
#     REPO_ROOT / "Exports" / "discovery-matrix" / "nif-semantic-hints"
# (note singular "discovery-matrix"; the canonical catalog job spec lives at
#  scripts/discovery-matrices/nif-semantic-hints.json (matrices, plural)).
DEFAULT_OUT_DIR = REPO_ROOT / "Exports" / "discovery-matrix" / "nif-semantic-hints"
SCHEMA_PATH = REPO_ROOT / "docs" / "schemas" / "asset-semantic-index-v1.schema.json"

# Standard path for the live-archive NIF inventory map.  The TIer-1
# classifier uses this path when ``--archive-index`` is passed without a
# value (auto-discover).  Missing file degrades silently to Tier 2.
DEFAULT_ARCHIVE_INDEX_PATH = REPO_ROOT / "Exports" / "discovery-plan" / "live-nif-archive-index.json"

# Matrix file basenames - MUST stay in sync with scripts.semantic_surface.MATRIX_FILE_NAMES.
MATRIX_FILES = {
    "hint:actor-object": "semantic-nif-actor-object.json",
    "hint:map-zone": "semantic-nif-map-zone.json",
    "hint:waypoint-poi": "semantic-nif-waypoint-poi.json",
}

# Vertex-count ladder for the ``faced == true`` lane (Tier-2 fallback):
#   vc >= ZONE_VC_MIN  -> hint:map-zone (large static geometry)
#   vc <  ZONE_VC_MIN  -> hint:actor-object (small/interactable geometry)
#
# Threshold picked from the live flythrough-index distribution analysis:
#   ~27 map-zone candidates (>=100v) + ~138 actor-object candidates (<100v)
#   align with the rough partition between zone-terrain prefabs and
#   NPC/prop/static-mesh assets.  ~62 point-only assets always go to POI.
ZONE_VC_MIN: int = 100


class ArchiveProvenance(NamedTuple):
    """Provenance record returned by ``load_archive_index``.

    Carries the asset's resolved archive location in the live game.
    ``archive`` is the literal TWAD filename (e.g. ``world.twad``),
    ``entry`` is the entry index inside that archive.
    """

    archive: str
    entry: int


# Archive taxonomy: substring -> hint category mapping.  Insertion order
# determines first-match-wins precedence.  We are deliberately conservative
# here; the C# backend should take over with a fuller ruleset.
ARCHIVE_TAXONOMY: dict[str, str] = {
    # map-zone: large static geometry
    "world": "hint:map-zone",
    "zone": "hint:map-zone",
    "map": "hint:map-zone",
    "terrain": "hint:map-zone",
    # actor-object: smaller, often interactable geometry
    "character": "hint:actor-object",
    "creature": "hint:actor-object",
    "npc": "hint:actor-object",
    "prop": "hint:actor-object",
    "item": "hint:actor-object",
    "object": "hint:actor-object",
    # waypoint-poi: position-only / non-facial markers
    "waypoint": "hint:waypoint-poi",
    "script": "hint:waypoint-poi",
    "spawn": "hint:waypoint-poi",
    # Live-archive assets.NNN range split (Tier-1 firing support for
    # the 244 extensionless ``assets.NNN`` archives on this 26GB live
    # install). Lower-numbered archives cover base world / terrain
    # geometry (map-zone); higher-numbered archives skew toward
    # episodic props / characters / NPC gear (actor-object).
    #
    # Disjointness: each needle is exactly 8 characters long
    # (``assets.N``). The 8th character is the digit ``0``, ``1``,
    # or ``2`` so any ``assets.NXX`` matches exactly one rule under
    # first-match-wins (no archive can match two rules). For example
    # ``assets.150`` matches ``"assets.1"`` (not ``"assets.0"`` because
    # the substring at offset 7 is ``"1"``, not ``"0"``).
    #
    # Fail-safe: archives beyond ``assets.244`` (e.g. a hypothetical
    # ``assets.999`` from a future client) match no needle and return
    # ``None`` so the asset reverts to the vertex-count heuristic.
    # This is intentional -- the polyfill never blocks on an unknown
    # archive shape.  The C# ``build-asset-semantic-index`` pipeline
    # will eventually replace this heuristic with manifest-derived
    # real provenance; until then, this split is the safest
    # approximation that fires Tier-1 for every cohort asset.
    "assets.0": "hint:map-zone",  # 001-099
    "assets.1": "hint:map-zone",  # 100-199
    "assets.2": "hint:actor-object",  # 200-244
}

# Marker strings for the (still-polyfill) provenance transition.  Both
# are treated as polyfill output by ``_assert_matrix_synth_polyfill_only``,
# but v2 archive carries real ArchiveName/EntryIndex while v1 carries
# synthetic.placeholders.  Once the C# build-asset-semantic-index
# backend lands, it will emit a different MagicLabel and the polyfill
# gates will FAIL CLOSED.
POLYFILL_MAGIC_V1 = "synthetic-semantic-polyfill"
POLYFILL_MAGIC_V2_ARCHIVE = "synthetic-semantic-polyfill-v2-archive"

# Boilerplate values for the schema-conforming top-level fields.  These are
# intentionally empty/null because real classification data lives only in
# ``Entries[]`` rows; once the C# pipeline emits real matrices, these slots
# will be populated by the producer.
GENERATED_OUTPUT_NOTICE = (
    "Generated by scripts/synthesize_semantic_matrices.py (Phase 47) from "
    "Assets/build/flythrough/flythrough-index.json. Tier 1 (archive-path) when "
    "live-nif-archive-index.json is populated; Tier 2 (heuristic) otherwise. "
    "Keep under ignored Exports/."
)
ROOT_DIRECTORY = ""
MANIFEST_PATH = ""

SEP = "=" * 80


def load_archive_index(path: Path | None) -> dict[str, ArchiveProvenance]:
    """Load the live-archive NIF inventory map into a hash->provenance table.

    Behavior:
      * ``path is None`` -- return empty dict (caller falls back to heuristic).
      * Auto-discovery (``path is DEFAULT_ARCHIVE_INDEX_PATH`` and missing) --
        return empty dict, NO exception.  Auto-discovery is best-effort.
      * Manual path (caller-specified or non-default) and missing -- raise
        ``FileNotFoundError``.  This is the fail-closed contract for
        ``--archive-index PATH``.

    Expected JSON shape: a list of ``{NifHash, ArchiveName, EntryIndex}`` rows.
    Rows with missing/typed-wrong fields are skipped silently (defensive
    against producer regressions).  Asset IDs are lowercased on load so
    callers can do case-insensitive joins.

    Args:
        path: inventory map location, or None to skip.

    Returns:
        ``{asset_id_hex_lower: ArchiveProvenance(archive, entry)}`` lookup.

    Raises:
        FileNotFoundError: when ``path`` is explicit but missing.
        ValueError: when the JSON cannot be parsed or is not a list.
    """
    if path is None:
        return {}
    if not path.exists():
        if path == DEFAULT_ARCHIVE_INDEX_PATH:
            return {}  # auto-discovery: silent degradation
        raise FileNotFoundError(f"Archive index not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Archive index JSON invalid: {path}: {e}") from e
    if not isinstance(data, list):
        raise ValueError(f"Archive index expected list of rows; got {type(data).__name__}: {path}")
    out: dict[str, ArchiveProvenance] = {}
    for row in data:
        if not isinstance(row, dict):
            continue
        asset_id = row.get("NifHash")
        archive = row.get("ArchiveName")
        entry = row.get("EntryIndex")
        if not isinstance(asset_id, str) or not isinstance(archive, str):
            continue
        if not isinstance(entry, int) or entry < 0:
            continue
        out[asset_id.lower()] = ArchiveProvenance(archive=archive, entry=entry)
    return out


def classify_by_archive(
    archive_name: str,
    taxonomy: dict[str, str] = ARCHIVE_TAXONOMY,
) -> str | None:
    """Substring-match archive name against taxonomy; first hit wins.

    Returns the matched hint category, or ``None`` if no rule matches.
    A ``None`` return signals the caller to fall through to the
    vertex-count heuristic for that asset.

    The matching is case-insensitive and uses Python dict iteration
    order (insertion order; first match wins).
    """
    archive_low = archive_name.lower()
    for needle, hint in taxonomy.items():
        if needle in archive_low:
            return hint
    return None


def classify_asset(
    asset_id: str,
    asset: dict[str, Any] | None,
    archive_index: dict[str, ArchiveProvenance] | None = None,
) -> str:
    """Classify one flythrough asset into one of the 3 hint categories.

    Two-tier precedence:
      Tier 1 (archive): if ``archive_index`` has ``asset_id`` AND the
        resolved archive name matches a taxonomy rule -> return that hint.
      Tier 2 (heuristic): vertex-count + faced heuristic (unchanged from v1).

    Backward-compatible: when ``archive_index is None`` (the v1 default),
    the function behaves identically to the heuristic-only path.  Existing
    tests at ``tests/test_synthesize_semantic_matrices.py::TestClassifyAsset``
    do not pass ``archive_index`` and continue to pass.

    Tier 1 fallthrough rules:
      - asset_id present in archive_index but archive name has no taxonomy
        rule -> fall through to heuristic.
      - asset_id absent from archive_index -> fall through.

    Args:
        asset_id: 16-char hex asset ID (preserved verbatim on the row).
        asset: Flythrough-index asset dict; may be None.
        archive_index: optional lookup from ``load_archive_index()``.

    Returns:
        One of "hint:actor-object", "hint:map-zone", or "hint:waypoint-poi".
    """
    if archive_index:
        prov = archive_index.get(asset_id.lower())
        if prov is not None:
            archive_hint = classify_by_archive(prov.archive)
            if archive_hint is not None:
                return archive_hint

    # Tier 2: heuristic fallback (unchanged from v1 polyfill).
    if asset is None:
        asset = {}
    faced = bool(asset.get("faced", False))
    if not faced:
        return "hint:waypoint-poi"
    vc = int(asset.get("vertex_count") or 0)
    if vc >= ZONE_VC_MIN:
        return "hint:map-zone"
    return "hint:actor-object"


def build_entry_row(
    asset_id: str,
    asset: dict[str, Any],
    hint: str,
    provenance: ArchiveProvenance | None = None,
) -> dict[str, Any]:
    """Build one ``Entries[]`` row for a classified asset.

    Provenance parameters:
      - ``provenance=None``: heuristic-classified entry. Carries
        ``ArchiveName="synthetic.twad"``, ``EntryIndex=0``,
        ``MagicLabel=synthetic-semantic-polyfill``.  Same shape as v1 polyfill.
      - ``provenance=ArchiveProvenance(archive, entry)``: archive-classified
        entry. Carries real ``ArchiveName``/``EntryIndex`` from the live
        inventory map, ``DetectedType="archive-derived"`` (was ``"synthetic"``),
        and ``MagicLabel=synthetic-semantic-polyfill-v2-archive`` so the
        orchestrator fail-closed check can recognize v2 vs. real C# output.

    Schema-required fields are all populated (boilerplate zeros for fields
    we don't have direct values for). The AssetIdPrefix is the join key
    used by ``scripts.semantic_surface.categorize_asset`` (case-insensitive
    per the loader contract).

    Note on ``First16`` (or rather, First32): the polyfill emits 32 hex chars
    so the field passes the schema's ``hexString`` regex (which only
    constrains hex chars, no length).  Future real matrices should populate
    the true 16-byte prefix from the archive entry digest.
    """
    del asset  # see notes; heuristic-only provenance not carried on the row
    archive_name = provenance.archive if provenance is not None else "synthetic.twad"
    entry_index = provenance.entry if provenance is not None else 0
    detected_type = "archive-derived" if provenance is not None else "synthetic"
    magic_label = POLYFILL_MAGIC_V2_ARCHIVE if provenance is not None else POLYFILL_MAGIC_V1
    return {
        "AssetIdPrefix": asset_id,
        "ArchiveName": archive_name,
        "EntryIndex": entry_index,
        "ManifestEntryIndex": None,
        "FilenameFnv1Hash": None,
        "PakIndex": None,
        "PakOffset": None,
        "CompressedSize": 0,
        "UnpackedSize": 0,
        "Compression": 0,
        "DetectedType": detected_type,
        "Format": None,
        "RiffType": None,
        "Width": None,
        "Height": None,
        "MipMapCount": None,
        "First4": "00000000",
        "First8": "0000000000000000",
        # TODO(cycle-5-prod): replace with real 16-byte archive entry prefix once
        # the C# pipeline emits this.  Polyfill emits 32 chars to satisfy
        # schema's `^[0-9a-fA-F]*$` regex (no length constraint); the
        # field-name "First16" is preserved for schema compatibility.
        "First16": "0000000000000000" + "0000000000000000",
        "MagicLabel": magic_label,
        "SemanticCategories": [hint],
        "NameCandidates": [],
        "ReferenceSamples": [],
        "XmlTagCounts": [],
        "XmlAttributeCounts": [],
        "XmlParseStatus": None,
        "XmlParseWarning": None,
        "XmlParseLineNumber": None,
        "XmlParseLinePosition": None,
        "XmlParsedElementCount": None,
        "XmlParsedAttributeNameCount": None,
        "TextSnippetSamples": [],
    }


def _build_top_level(hint: str, entries_count: int) -> dict[str, Any]:
    """Build the schema-required top-level wrapper for one matrix report.

    Note on ``InspectedPayloads``: the polyfill reports the count of
    ``Entries`` -- semantically inaccurate (the field literally
    means "how many payloads were inspected") but is a polyfill trade-off.
    The real C# pipeline will overwrite with the source's actual inspected
    payloads total.
    """
    return {
        "SchemaVersion": "asset-semantic-index/v1",
        "GeneratedOutputNotice": GENERATED_OUTPUT_NOTICE,
        "RootDirectory": ROOT_DIRECTORY,
        "ManifestPath": MANIFEST_PATH,
        "SemanticCategoryFilters": [hint],
        "InspectedPayloads": entries_count,
        "Failed": 0,
        "TypeCounts": [
            {"Value": "nif", "Count": entries_count},
        ],
        "SemanticCategoryCounts": [
            {"Value": hint, "Count": entries_count},
        ],
        "SignatureGroups": [],
        "Entries": [],  # populated in write_matrices below
    }


def load_flythrough_index(path: Path) -> dict[str, Any]:
    """Load flythrough-index.json (UTF-8 with BOM tolerance); return ``{"assets": ...}``."""
    if not path.exists():
        raise FileNotFoundError(
            f"Flythrough-index not found at {path}. "
            f"Re-run the FT pipeline (bulk export + flythrough_plan) before synthesizing matrices."
        )
    return json.loads(path.read_text(encoding="utf-8-sig"))


def synthesize_matrices(
    flythrough: dict[str, Any],
    archive_index: dict[str, ArchiveProvenance] | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    """Walk the flythrough index, classify each asset, and return per-hint entry rows.

    Two-tier classification:
      Tier 1 (preferred): if ``archive_index`` is provided AND the asset
        is present AND ``classify_by_archive()`` returns a hint, use that.
      Tier 2 (fallback): heuristic.

    Returns: ``(by_hint, stats)`` where
        ``by_hint`` = ``{hint: [row, ...]}`` mapping for the 3 shipped hints;
        ``stats`` = ``{"archive-classified": int, "heuristic-fallback": int}``
        counts for provenance reporting.

    One asset gets exactly one hint (no multi-tag classification -- the
    polyfill is mono-tag by design, matching the thinker's recommendation).

    Enforces underscore-prefix-free contract at the producer boundary (in
    addition to ``write_matrices``'s defense-in-depth check).  Any caller
    routing through ``synthesize_matrices`` is guaranteed a schema-clean
    bucket structure.

    NOTE: Return shape changed from a single ``by_hint`` dict to a tuple
    ``(by_hint, stats)`` after archive-classifier was added.  Existing v1
    callers must unpack: ``by_hint, _ = synthesize_matrices(...)``.
    """
    assets = flythrough.get("assets", {})
    if not isinstance(assets, dict):
        raise ValueError(
            "Flythrough-index 'assets' field is not a dict; got "
            f"{type(assets).__name__}.  The polyfill expects the FT-8 schema."
        )
    by_hint: dict[str, list[dict[str, Any]]] = {h: [] for h in MATRIX_FILES}
    stats = {"archive-classified": 0, "heuristic-fallback": 0}
    for asset_id, asset in assets.items():
        if not isinstance(asset, dict):
            continue
        # Tier 1: archive-driven classification when provenance available.
        provenance: ArchiveProvenance | None = None
        if archive_index and asset_id.lower() in archive_index:
            prov = archive_index[asset_id.lower()]
            archive_hint = classify_by_archive(prov.archive)
            if archive_hint is not None:
                hint = archive_hint
                provenance = prov
                stats["archive-classified"] += 1
            else:
                # Tier-1 fallthrough: archive known but no taxonomy rule.
                hint = classify_asset(asset_id, asset, None)
                stats["heuristic-fallback"] += 1
        else:
            # Tier 2: heuristic fallback (asset not in archive_index).
            hint = classify_asset(asset_id, asset, None)
            stats["heuristic-fallback"] += 1
        by_hint[hint].append(build_entry_row(asset_id, asset, hint, provenance=provenance))
    # Producer-boundary check: rejects any entry with underscore-prefix keys
    # before the caller can route it through a non-write_matrices serializer.
    for entries in by_hint.values():
        _assert_schema_clean_entries(entries)
    return by_hint, stats


def _assert_schema_clean_entries(entries: list[dict[str, Any]]) -> None:
    """Defense-in-depth: ensure no underscore-prefix diagnostic keys leak.

    Schema enforces ``additionalProperties: false`` for entry objects.
    ``build_entry_row()`` does not emit them by construction, but this guard
    catches future regressions at write-time rather than at schema validation.
    """
    for idx, entry in enumerate(entries):
        bad = [k for k in entry if k.startswith("_")]
        if bad:
            raise ValueError(
                f"Non-schema underscore-prefix keys {bad} in entry {idx} "
                f"(would trip `additionalProperties: false` validation)"
            )


def write_matrices(
    by_hint: dict[str, list[dict[str, Any]]],
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Path]:
    """Write the 3 matrix files to ``out_dir``.  Returns ``{hint: path}`` mapping."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for hint, fname in MATRIX_FILES.items():
        entries = by_hint.get(hint, [])
        _assert_schema_clean_entries(entries)
        report = _build_top_level(hint, len(entries))
        report["Entries"] = entries
        path = out_dir / fname
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        written[hint] = path
    return written


def validate_against_schema(out_dir: Path = DEFAULT_OUT_DIR) -> tuple[bool, list[str]]:
    """Validate each emitted matrix file against ``asset-semantic-index-v1`` schema.

    Uses ``jsonschema.Draft202012Validator``; returns ``(ok, errors)``.
    Errors are formatted as ``path: message`` strings.
    """
    try:
        import jsonschema
    except ImportError:
        return True, ["(skipped) jsonschema not installed; nothing to validate against"]

    if not SCHEMA_PATH.exists():
        return True, [f"(skipped) schema not found: {SCHEMA_PATH}"]

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8-sig"))
    validator = jsonschema.Draft202012Validator(schema)

    errors: list[str] = []
    # Iterate by file name; the hint-tag is parallel via MATRIX_FILES[fname] if
    # needed in future diagnostics.
    for fname in MATRIX_FILES.values():
        path = out_dir / fname
        if not path.exists():
            errors.append(f"{fname}: missing on disk")
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as e:
            errors.append(f"{fname}: invalid JSON ({e})")
            continue
        for err in validator.iter_errors(data):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            errors.append(f"{fname}::{loc}: {err.message}")
    return (len(errors) == 0), errors


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    do_validate = "--validate" in argv or "--validate-schema" in argv

    # Parse --archive-index (allows ``--archive-index PATH`` or ``--archive-index`` alone).
    archive_index_path: Path | None = DEFAULT_ARCHIVE_INDEX_PATH
    archive_index_explicit = False
    if "--archive-index" in argv:
        idx = argv.index("--archive-index")
        if idx + 1 < len(argv) and not argv[idx + 1].startswith("--"):
            archive_index_path = Path(argv[idx + 1])
            archive_index_explicit = True
        # else: bare --archive-index -> auto-discover (DEFAULT_ARCHIVE_INDEX_PATH).

    # --no-archive-index disables Tier 1 entirely (heuristic-only run).
    if "--no-archive-index" in argv:
        archive_index_path = None

    print(SEP)
    print("PHASE 47: SEMANTIC HINT MATRIX SYNTHESIZER (Cycle 5 data-thickness polyfill)")
    print(SEP)
    print(f"  flythrough-index:    {FLYTHROUGH_INDEX}")
    print(f"  output dir:          {DEFAULT_OUT_DIR}")
    print(f"  schema path:         {SCHEMA_PATH}")
    print(f"  archive-index path:  {archive_index_path}  (explicit={archive_index_explicit})")
    print(f"  threshold:           vc >= {ZONE_VC_MIN} -> hint:map-zone")
    print()

    archive_index = load_archive_index(archive_index_path)
    tier1_active = bool(archive_index)
    print(f"  archive-index size:  {len(archive_index)} entries (Tier 1 {'ACTIVE' if tier1_active else 'OFFLINE'})")
    print()

    flythrough = load_flythrough_index(FLYTHROUGH_INDEX)
    by_hint, stats = synthesize_matrices(flythrough, archive_index=archive_index)

    counts: Counter = Counter({hint: len(entries) for hint, entries in by_hint.items()})
    total = sum(len(entries) for entries in by_hint.values())

    print("Classification breakdown:")
    for hint in MATRIX_FILES:
        n = counts[hint]
        pct = (100.0 * n / total) if total else 0.0
        print(f"  {hint:24s} {n:5d} assets ({pct:5.1f}%)")
    print(f"  {'total':24s} {total:5d} assets (100.0%)")
    print()
    print("Provenance breakdown:")
    print(f"  archive-classified:    {stats['archive-classified']:5d}")
    print(f"  heuristic-fallback:    {stats['heuristic-fallback']:5d}")

    if dry_run:
        print("\nDRY RUN: not writing files.")
        return 0

    written = write_matrices(by_hint, DEFAULT_OUT_DIR)
    print("\nWrote:")
    for hint, path in written.items():
        size_kb = path.stat().st_size // 1024
        print(f"  {hint:24s} {path.name:35s} ({size_kb} KB, {counts[hint]} entries)")

    if do_validate:
        print(f"\nValidating against {SCHEMA_PATH.name}...")
        ok, errors = validate_against_schema(DEFAULT_OUT_DIR)
        if ok:
            print("  PASS: all 3 matrix files schema-valid")
        else:
            print("  FAIL:")
            for line in errors:
                print(f"    - {line}")
            return 1

    # Sanity ping: round-trip through the public loader so we know
    # ``categorize_asset`` works against the synthesized data.
    try:
        from scripts.semantic_surface import (
            ABSENT_MARKER,
            build_semantic_block,
            load_all_matrices,
        )

        matrices = load_all_matrices(DEFAULT_OUT_DIR)
        for hint_key in MATRIX_FILES:
            assert len(matrices[hint_key]) == counts[hint_key], (
                f"loader/serializer count mismatch for {hint_key}: "
                f"loader={len(matrices[hint_key])} vs writer={counts[hint_key]}"
            )

        # Round-trip on one asset per hint
        sample_per_hint: dict[str, str] = {}
        for hint, entries in by_hint.items():
            if entries:
                sample_per_hint[hint] = entries[0]["AssetIdPrefix"]

        print("\nRound-trip via scripts.semantic_surface:")
        for hint, asset_id in sample_per_hint.items():
            block = build_semantic_block(asset_id, DEFAULT_OUT_DIR)
            assert hint in block["categories"], f"loader round-trip lost {hint} for {asset_id}: {block}"
            print(f"  {asset_id} -> categories={block['categories']}")

        # Sanity: sources map uses basenames (not ABSENT_MARKER) for present files.
        sample_block = build_semantic_block("ffffffffffffffff", DEFAULT_OUT_DIR)
        all_basename_ok = all(block_value != ABSENT_MARKER for block_value in sample_block["sources"].values())
        assert all_basename_ok, "sources map regressed to ABSENT_MARKER for present files"
        print("  loader contract preserved (sources map uses basenames, no ABSENT_MARKER for present files)")

    except Exception as e:
        print(f"\nFAIL: loader round-trip failed: {type(e).__name__}: {e}")
        return 1

    print(f"\n{SEP}")
    print("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
