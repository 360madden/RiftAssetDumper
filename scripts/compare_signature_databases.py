#!/usr/bin/env python3
"""Phase 6 diff tool: compare two unified binary-signature databases.

Reads two versioned ``rift-x64-signature-database.json`` files produced by the
Phase 5 synth (or any archive of an earlier unified DB) and emits a structured
diff report that names every category of change. The output JSON is the
"patch-diff-report" that tells RiftReader what needs updating when a game
patch lands.

Categories reported (see ``DiffCategory`` enum in the schema)::

    binary-version-changed     PETimestamp/FileSizeBytes differ (game patch!)
    binary-fingerprint-moved   PE image-base or text-section raw size changed
    anchor-added               anchor in new DB but not old DB
    anchor-removed             anchor in old DB but not new DB
    sig-hex-changed            wildcarded signature bytes differ (sig MUST change noticeably)
    signature-length-changed   signature length differs (wildcards added or removed)
    wildcard-count-changed     number of ? wildcards differs (more aggressive lg cmask)
    stability-tier-regressed   StabilityTier shifted (higher tier = less stable)
    uniqueness-changed         UniquenessVerified flipped (sig no longer 1 match in .text)
    struct-fields-added        new field discovered in any StructLayout
    struct-fields-removed      field vanished (game changed struct shape)
    modrm-shake                per-field ModRMHitCount changed by >25% (refactor)
    notes-changed              free-form Notes string differs
    confidence-promoted        Confidence upgraded (inferred -> confirmed)
    confidence-demoted         Confidence downgraded (confirmed -> inferred)
    ghidra-findings-changed    Provenance.GhidraFindings dict changed

Usage::

    python scripts/compare_signature_databases.py \\
        --old-db Exports/binary-phase5/rift-x64-signature-database.v1.json \\
        --new-db Exports/binary-phase5/rift-x64-signature-database.json \\
        --out Exports/binary-phase6/patch-diff-report.json

Exit codes:
    0 — diff computed (regardless of churn)
    1 — schema validation failure on either input DB
    2 — IO / parse error
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

DIFF_REPORT_SCHEMA = "binary-signature-diff/v1"
MODRM_SHAKE_THRESHOLD = 0.25  # 25% delta qualifies a hit-count change as a 'shake'


@dataclass
class Categories:
    """Per-category counter; total = sum of per-category counts."""

    counts: dict[str, int] = field(default_factory=dict)

    def add(self, category: str, n: int = 1) -> None:
        self.counts[category] = self.counts.get(category, 0) + n


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_input(doc: dict[str, Any], *, label: str) -> list[str]:
    schema_path = REPO_ROOT / "docs" / "schemas" / "binary-signatures-v1.schema.json"
    if not schema_path.exists():
        return []
    try:
        import jsonschema

        jsonschema.validate(
            doc,
            json.loads(schema_path.read_text(encoding="utf-8")),
            format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER,
        )
    except ImportError:
        # jsonschema not installed: emit a WARNING so CI on minimal installs
        # doesn't silently ship schema-broken artifacts. The lightweight fallback
        # only verifies Anchors[] presence — sufficient for diff core but does
        # not guarantee full schema conformance.
        print(
            f"WARNING: jsonschema unavailable; {label} falling back to structural minimum check",
            file=sys.stderr,
        )
        if not isinstance(doc.get("Anchors"), list):
            return [f"{label}: missing Anchors[]"]
    except jsonschema.ValidationError as exc:
        return [f"{label}: {exc.message}"]
    return []


def _by_name(anchors: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {a.get("Name", ""): a for a in anchors if a.get("Name")}


def _compare_provenance(
    old: dict[str, Any], new: dict[str, Any], out: Categories, changes: list[dict[str, Any]]
) -> None:
    """Diff Provenance.BinaryVersion, TextSection, GhidraFindings."""
    old_bv = old.get("BinaryVersion") or {}
    new_bv = new.get("BinaryVersion") or {}
    bv_diff_keys = [k for k in ("PETimestamp", "FileSizeBytes") if old_bv.get(k) != new_bv.get(k)]
    if bv_diff_keys:
        out.add("binary-version-changed")
        changes.append({"category": "binary-version-changed", "fields": bv_diff_keys, "old": old_bv, "new": new_bv})

    old_im = old.get("ImageBase", "")
    new_im = new.get("ImageBase", "")
    old_text = (old.get("TextSection") or {}).get("RawSize", 0)
    new_text = (new.get("TextSection") or {}).get("RawSize", 0)
    if old_im != new_im or old_text != new_text:
        out.add("binary-fingerprint-moved")
        changes.append(
            {
                "category": "binary-fingerprint-moved",
                "old_image": old_im,
                "new_image": new_im,
                "old_text": old_text,
                "new_text": new_text,
            }
        )

    old_gf = old.get("Provenance", {}).get("GhidraFindings", {})
    new_gf = new.get("Provenance", {}).get("GhidraFindings", {})
    if old_gf != new_gf:
        out.add("ghidra-findings-changed")
        changes.append({"category": "ghidra-findings-changed", "old": old_gf, "new": new_gf})


def _compare_anchor(
    name: str,
    old: dict[str, Any] | None,
    new: dict[str, Any] | None,
    out: Categories,
    changes: list[dict[str, Any]],
) -> None:
    """Diff a single anchor (keyed by name) between old and new."""
    if old is None and new is not None:
        out.add("anchor-added")
        changes.append({"category": "anchor-added", "name": name, "anchor": new})
        return
    if new is None and old is not None:
        out.add("anchor-removed")
        changes.append({"category": "anchor-removed", "name": name, "anchor": old})
        return
    if old is None or new is None:
        return

    sig_old = old.get("SignatureHex", "")
    sig_new = new.get("SignatureHex", "")
    if sig_old != sig_new:
        out.add("sig-hex-changed")
        changes.append({"category": "sig-hex-changed", "name": name, "old": sig_old, "new": sig_new})

    if old.get("SignatureLength") != new.get("SignatureLength"):
        out.add("signature-length-changed")
        changes.append({"category": "signature-length-changed", "name": name})

    if old.get("WildcardCount") != new.get("WildcardCount"):
        out.add("wildcard-count-changed")
        changes.append({"category": "wildcard-count-changed", "name": name})

    tier_old = old.get("StabilityTier", 99)
    tier_new = new.get("StabilityTier", 99)
    if tier_old != tier_new:
        if tier_new > tier_old:
            out.add("stability-tier-regressed")
            changes.append(
                {
                    "category": "stability-tier-regressed",
                    "name": name,
                    "old": tier_old,
                    "new": tier_new,
                }
            )

    if old.get("UniquenessVerified") != new.get("UniquenessVerified"):
        out.add("uniqueness-changed")
        changes.append({"category": "uniqueness-changed", "name": name, "was_unique": old.get("UniquenessVerified")})

    _compare_struct_layout(name, old.get("StructLayout"), new.get("StructLayout"), out, changes)


def _compare_struct_layout(
    anchor_name: str,
    old: dict[str, Any] | None,
    new: dict[str, Any] | None,
    out: Categories,
    changes: list[dict[str, Any]],
) -> None:
    if old is None and new is not None:
        out.add("struct-fields-added")
        changes.append(
            {
                "category": "struct-fields-added",
                "anchor_name": anchor_name,
                "fields": [f.get("Name") for f in new.get("Fields", [])],
            }
        )
        return
    if new is None and old is not None:
        out.add("struct-fields-removed")
        changes.append(
            {
                "category": "struct-fields-removed",
                "anchor_name": anchor_name,
                "fields": [f.get("Name") for f in old.get("Fields", [])],
            }
        )
        return
    if old is None or new is None:
        return

    old_fields = _by_offset(old.get("Fields", []))
    new_fields = _by_offset(new.get("Fields", []))
    added_offsets = set(new_fields) - set(old_fields)
    removed_offsets = set(old_fields) - set(new_fields)
    if added_offsets:
        out.add("struct-fields-added", n=len(added_offsets))
        changes.append(
            {
                "category": "struct-fields-added",
                "anchor_name": anchor_name,
                "offsets": sorted(added_offsets),
            }
        )
    if removed_offsets:
        out.add("struct-fields-removed", n=len(removed_offsets))
        changes.append(
            {
                "category": "struct-fields-removed",
                "anchor_name": anchor_name,
                "offsets": sorted(removed_offsets),
            }
        )

    for offset in set(old_fields) & set(new_fields):
        old_f = old_fields[offset]
        new_f = new_fields[offset]
        # Field-Name drift: same offset, different semantic name. Critical for
        # RiftReader fallback consumers that compare structured fields; surfaced
        # even when SignatureHex + ModRMHitCount are unchanged.
        if old_f.get("Name") != new_f.get("Name"):
            out.add("field-name-changed")
            changes.append(
                {
                    "category": "field-name-changed",
                    "anchor_name": anchor_name,
                    "offset": offset,
                    "old": old_f.get("Name"),
                    "new": new_f.get("Name"),
                }
            )
        # ModRMHitCount shake: >=25% delta counts as a refactor
        oh = int(old_f.get("ModRMHitCount") or 0)
        nh = int(new_f.get("ModRMHitCount") or 0)
        if oh or nh:
            delta_pct = abs(nh - oh) / max(oh, nh, 1)
            if delta_pct >= MODRM_SHAKE_THRESHOLD:
                out.add("modrm-shake")
                changes.append(
                    {
                        "category": "modrm-shake",
                        "anchor_name": anchor_name,
                        "field": new_f.get("Name"),
                        "offset": offset,
                        "old": oh,
                        "new": nh,
                        "delta_pct": round(delta_pct, 3),
                    }
                )
        if old_f.get("Notes") != new_f.get("Notes"):
            out.add("notes-changed")
            changes.append(
                {
                    "category": "notes-changed",
                    "anchor_name": anchor_name,
                    "field": new_f.get("Name"),
                    "offset": offset,
                }
            )
        _compare_confidence(
            anchor_name,
            new_f.get("Name"),
            offset,
            old_f.get("Confidence"),
            new_f.get("Confidence"),
            out,
            changes,
        )


def _by_offset(fields: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {f.get("OffsetHex", ""): f for f in fields if f.get("OffsetHex")}


def _compare_confidence(
    anchor_name: str,
    field_name: str | None,
    offset: str,
    old_c: str | None,
    new_c: str | None,
    out: Categories,
    changes: list[dict[str, Any]],
) -> None:
    rank = {"tentative": 0, "inferred": 1, "confirmed": 2}
    if old_c == new_c or old_c is None or new_c is None:
        return
    old_r = rank.get(old_c, -1)
    new_r = rank.get(new_c, -1)
    if new_r > old_r:
        out.add("confidence-promoted")
        changes.append(
            {
                "category": "confidence-promoted",
                "anchor_name": anchor_name,
                "field": field_name,
                "offset": offset,
                "old": old_c,
                "new": new_c,
            }
        )
    else:
        out.add("confidence-demoted")
        changes.append(
            {
                "category": "confidence-demoted",
                "anchor_name": anchor_name,
                "field": field_name,
                "offset": offset,
                "old": old_c,
                "new": new_c,
            }
        )


def compute_diff(old_db: dict[str, Any], new_db: dict[str, Any]) -> dict[str, Any]:
    """Compute a categorized diff between two unified DBs."""
    cats = Categories()
    changes: list[dict[str, Any]] = []
    _compare_provenance(old_db, new_db, cats, changes)

    old_by_name = _by_name(old_db.get("Anchors", []))
    new_by_name = _by_name(new_db.get("Anchors", []))
    all_names = sorted(set(old_by_name) | set(new_by_name))
    for name in all_names:
        _compare_anchor(name, old_by_name.get(name), new_by_name.get(name), cats, changes)

    return {
        "diff_categories": sorted(cats.counts),
        "total_changes": sum(cats.counts.values()),
        "category_counts": cats.counts,
        "changes": changes,
    }


def render_markdown(report: dict[str, Any], *, old_path: str, new_path: str) -> str:
    lines = [
        "# Binary-signature diff report",
        "",
        f"Old: `{old_path}`",
        f"New: `{new_path}`",
        f"Total changes: **{report['total_changes']}** across {len(report['diff_categories'])} categories",
        "",
        "## Category counts",
        "",
    ]
    for cat, count in sorted(report["category_counts"].items()):
        lines.append(f"- `{cat}`: **{count}**")
    lines.extend(["", "## Changes", ""])
    if not report["changes"]:
        lines.append("- (none)")
    else:
        for c in report["changes"]:
            lines.append(f"### `{c['category']}`")
            for k, v in c.items():
                if k == "category":
                    continue
                if isinstance(v, (dict, list)):
                    v = json.dumps(v)
                lines.append(f"- **{k}**: {v}")
            lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--old-db", type=Path, required=True, help="Path to old unified DB JSON.")
    parser.add_argument("--new-db", type=Path, required=True, help="Path to new unified DB JSON.")
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "Exports" / "binary-phase6" / "patch-diff-report.json",
        help="Output path for the diff JSON report.",
    )
    parser.add_argument(
        "--markdown-out",
        type=Path,
        default=None,
        help="Optional path for a human-readable Markdown report.",
    )
    args = parser.parse_args(argv)

    if not args.old_db.exists():
        print(f"ERROR: old DB not found: {args.old_db}", file=sys.stderr)
        return 2
    if not args.new_db.exists():
        print(f"ERROR: new DB not found: {args.new_db}", file=sys.stderr)
        return 2
    try:
        old_db = _load_json(args.old_db)
        new_db = _load_json(args.new_db)
    except Exception as exc:
        print(f"ERROR: parse failure on input: {exc}", file=sys.stderr)
        return 2

    p_old = _validate_input(old_db, label="old_db")
    if p_old:
        print("\n".join(p_old), file=sys.stderr)
        return 1
    p_new = _validate_input(new_db, label="new_db")
    if p_new:
        print("\n".join(p_new), file=sys.stderr)
        return 1

    diff = compute_diff(old_db, new_db)
    report = {
        "SchemaVersion": DIFF_REPORT_SCHEMA,
        "DiffExtractedAt": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "OldPath": str(args.old_db),
        "NewPath": str(args.new_db),
        **diff,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"==> Diff report: {args.out}")
    print(f"    Total changes: {report['total_changes']}")
    for cat, count in sorted(report["category_counts"].items()):
        print(f"      - {cat}: {count}")
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(
            render_markdown(diff, old_path=str(args.old_db), new_path=str(args.new_db)), encoding="utf-8"
        )
        print(f"==> Markdown: {args.markdown_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
