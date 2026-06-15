"""Tests for unresolved practical texture evidence audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from audit_flythrough_unresolved_texture_evidence import (  # noqa: E402
    build_unresolved_texture_evidence_report,
    render_markdown,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_build_unresolved_texture_evidence_report_counts_exact_and_asset_matches(tmp_path: Path) -> None:
    gap_report = tmp_path / "Assets" / "build" / "flythrough" / "evidence" / "gap.json"
    name_matches = tmp_path / "Exports" / "name-matches.jsonl"
    texture_links = tmp_path / "Exports" / "texture-links.jsonl"
    live_links = tmp_path / "Exports" / "live-links.jsonl"
    _write_json(
        gap_report,
        {
            "unmatched_exact_dds_refs": ["missing_wall_c.dds", "still_missing_s.dds"],
            "neutral_rows": [
                {"manifest_index": 10, "asset_id": "aaaaaaaaaaaaaaaa"},
                {"manifest_index": 11, "asset_id": "aaaaaaaaaaaaaaaa"},
                {"manifest_index": 12, "asset_id": "bbbbbbbbbbbbbbbb"},
                {"manifest_index": 13, "asset_id": None},
            ],
        },
    )
    _write_jsonl(
        name_matches,
        [
            {"Name": "missing_wall_c.dds", "IdPrefix": "cccccccccccccccc"},
            {"Name": "other.dds", "IdPrefix": "dddddddddddddddd"},
        ],
    )
    _write_jsonl(
        texture_links,
        [
            {
                "ModelIdPrefix": "aaaaaaaaaaaaaaaa",
                "Reference": "known_asset_texture.dds",
                "Candidate": "known_asset_texture.dds",
                "TextureIdPrefix": "eeeeeeeeeeeeeeee",
            }
        ],
    )
    _write_jsonl(live_links, [{"ModelIdPrefix": "bbbbbbbbbbbbbbbb", "Candidate": "live_texture.dds"}])

    report = build_unresolved_texture_evidence_report(
        repo_root=tmp_path,
        texture_gap_report_path=gap_report,
        name_matches_path=name_matches,
        texture_links_path=texture_links,
        live_texture_links_all4_path=live_links,
    )

    assert report["summary"]["unmatched_exact_dds_refs"] == 2
    assert report["summary"]["unmatched_exact_dds_refs_with_any_exact_match"] == 1
    assert report["summary"]["neutral_asset_ids"] == 2
    assert report["summary"]["neutral_asset_ids_with_texture_link_rows"] == 2
    exact = {row["dds_ref"]: row for row in report["exact_dds_refs"]}
    assert exact["missing_wall_c.dds"]["exact_match_count"] == 1
    assert exact["still_missing_s.dds"]["exact_match_count"] == 0
    assets = {row["asset_id"]: row for row in report["neutral_assets"]}
    assert assets["aaaaaaaaaaaaaaaa"]["manifest_indices"] == [10, 11]
    assert assets["aaaaaaaaaaaaaaaa"]["texture_link_row_count"] == 1
    assert assets["bbbbbbbbbbbbbbbb"]["texture_link_row_count"] == 1


def test_render_markdown_includes_negative_interpretation() -> None:
    markdown = render_markdown(
        {
            "generated_at": "2026-06-15T00:00:00Z",
            "summary": {
                "unmatched_exact_dds_refs": 1,
                "unmatched_exact_dds_refs_with_any_exact_match": 0,
                "neutral_asset_ids": 1,
                "neutral_asset_ids_with_texture_link_rows": 0,
                "neutral_rows": 2,
                "neutral_rows_with_asset_id": 1,
                "neutral_rows_without_asset_id": 1,
            },
            "source_stats": [
                {
                    "source": "texture-links",
                    "exists": True,
                    "scanned_lines": 10,
                    "candidate_lines": 0,
                    "parse_errors": 0,
                }
            ],
            "exact_dds_refs": [
                {
                    "dds_ref": "still_missing_s.dds",
                    "exact_match_count": 0,
                    "counts_by_source": {},
                }
            ],
            "neutral_assets": [
                {
                    "asset_id": "aaaaaaaaaaaaaaaa",
                    "manifest_indices": [1],
                    "texture_link_row_count": 0,
                    "counts_by_source": {},
                }
            ],
        }
    )

    assert "still_missing_s.dds" in markdown
    assert "zero exact matches remain unresolved" in markdown
    assert "aaaaaaaaaaaaaaaa" in markdown
