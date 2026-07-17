"""tests/test_build_all_navmeshes.py — M6.1 batch navmesh generator tests.

Covers the lightweight gates around build_all_navmeshes.py:
  - Pure logic: compute_zone_counts, select_eligible_zones, build_index_doc
  - Slugify parity with scripts/extract_zone_geometry._slugify
  - load_walkability tolerance for missing/malformed input
  - build_one_zone at each stage (mocked subprocess) -- extract failure,
    build failure, validate-stage failure (rc!=0), validate invalid report,
    validate success
  - Schema self-check: passes on a correct index; catches drift in stage enum,
    connected_zones sibling reference, skip_reason enum, bounds inversion.

Subprocess invocations are mocked via monkeypatch so these tests do NOT drive
the JVM or run real Recast builds. The end-to-end real-batch run is verified
manually + by CI on the full pipeline.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

# Ensure REPO_ROOT is on sys.path so `scripts.*` imports work.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest  # noqa: E402

from scripts import build_all_navmeshes as bam  # noqa: E402
from scripts.extract_zone_geometry import _slugify as ezm_slugify  # noqa: E402

# ---------- helpers ---------------------------------------------------------


def _make_completed_process(
    *, returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=[],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _synthetic_fly_index(zone_assignments: dict[str, tuple[int, int]]) -> dict[str, Any]:
    """Build a synthetic flythrough-index.json: {asset_id: {zone.tuple, ...}}.

    Args:
        zone_assignments: {zone_tuple: (num_walkable, num_non_walkable)}.
            The first N asset_ids mapped to the zone are 'walkable_*', the rest
            'non_walkable_*'. Assets receive walkability labels below.
    """
    assets: dict[str, Any] = {}
    counter = 0
    for zone_tuple, (n_walk, n_other) in zone_assignments.items():
        for _ in range(n_walk):
            aid = f"{zone_tuple.replace('.', '')}{counter:04d}w"
            assets[aid] = {
                "zone": {"tuple": zone_tuple, "confidence": "high"},
                "faced": True,
            }
            counter += 1
        for _ in range(n_other):
            aid = f"{zone_tuple.replace('.', '')}{counter:04d}n"
            assets[aid] = {
                "zone": {"tuple": zone_tuple, "confidence": "high"},
                "faced": True,
            }
            counter += 1
    return {"schema_version": "flythrough-index-v1", "assets": assets}


def _synthetic_walkability(
    fly_assets: dict[str, Any],
    *,
    walkable_labels: tuple[str, ...] = (
        "walkable_structure",
        "walkable_terrain",
        "walkable_floor",
        "walkable_platform",
        "potentially_walkable",
    ),
    other_label: str = "non_walkable_prop",
    first_n_walkable_per_zone: dict[str, int] | None = None,
) -> dict[str, str]:
    """Build a synthetic walkability dict that labels the first N assets per
    zone walkably; the rest get the other_label.

    If first_n_walkable_per_zone is None, all assets are 'walkable_structure'.
    """
    out: dict[str, str] = {}
    by_zone: dict[str, list[str]] = {}
    for aid, a in sorted(fly_assets.items()):
        zone = a.get("zone", {}).get("tuple", "")
        by_zone.setdefault(zone, []).append(aid)
    for zone, aids in by_zone.items():
        n_walk = first_n_walkable_per_zone.get(zone, len(aids)) if first_n_walkable_per_zone else len(aids)
        n_walk = min(n_walk, len(aids))
        for i, aid in enumerate(aids):
            if i < n_walk:
                out[aid] = walkable_labels[i % len(walkable_labels)]
            else:
                out[aid] = other_label
    return out


# ---------- slugify parity lock ---------------------------------------------


def test_slugify_matches_extract_zone_geometry_slugify() -> None:
    """If extract_zone_geometry._slugify ever changes, this test fails first."""
    cases = [
        "ep1.world_objects.dungeons",
        "ep2.world_objects.architecture",
        "vanilla.vfx.atmosphere",
        "ep1.character.common",
    ]
    for zt in cases:
        assert bam._slugify(zt) == ezm_slugify(zt), f"slugify drift on {zt!r}"


# ---------- compute_zone_counts ---------------------------------------------


def test_compute_zone_counts_with_synthetic_index_and_walkability() -> None:
    fly = _synthetic_fly_index(
        {
            "ep1.world_objects.dungeons": (7, 5),  # 7 walkable, 5 non-walkable
            "ep2.world_objects.architecture": (2, 3),  # 2 walkable, 3 other
            "ep1.character.common": (3, 0),  # all walkable
        }
    )
    walk = _synthetic_walkability(
        fly["assets"],
        first_n_walkable_per_zone={
            "ep1.world_objects.dungeons": 7,
            "ep2.world_objects.architecture": 2,
            "ep1.character.common": 3,
        },
    )
    walkable_counts, total_counts, missing = bam.compute_zone_counts(fly, walk)
    assert walkable_counts["ep1.world_objects.dungeons"] == 7
    assert walkable_counts["ep2.world_objects.architecture"] == 2
    assert walkable_counts["ep1.character.common"] == 3
    assert total_counts["ep1.world_objects.dungeons"] == 12
    assert total_counts["ep2.world_objects.architecture"] == 5
    assert total_counts["ep1.character.common"] == 3
    assert missing == [], "no assets should be missing classifications"


def test_compute_zone_counts_flags_missing_walkability() -> None:
    fly = _synthetic_fly_index({"ep1.world_objects.dungeons": (2, 1)})
    walk = _synthetic_walkability(
        fly["assets"],
        first_n_walkable_per_zone={"ep1.world_objects.dungeons": 2},
    )
    # Drop one asset from walkability to simulate missing-classification drift.
    drop_aid = sorted(fly["assets"].keys())[0]
    walk.pop(drop_aid, None)
    _, _, missing = bam.compute_zone_counts(fly, walk)
    assert missing == [drop_aid], missing


# ---------- select_eligible_zones threshold boundary -----------------------


def test_select_eligible_zones_threshold_boundary_inclusive() -> None:
    """A zone with walkable count == threshold is ELIGIBLE (>=)."""
    from collections import Counter

    walkable_counts: Counter = Counter({"zone.a": 5, "zone.b": 4, "zone.c": 6})
    eligible = bam.select_eligible_zones(walkable_counts, min_walkable=5)
    assert eligible == ["zone.a", "zone.c"]


def test_select_eligible_zones_threshold_one() -> None:
    from collections import Counter

    walkable_counts: Counter = Counter({"zone.x": 1, "zone.y": 0})
    eligible = bam.select_eligible_zones(walkable_counts, min_walkable=1)
    assert eligible == ["zone.x"]
    assert bam.select_eligible_zones(walkable_counts, min_walkable=2) == []


def test_select_eligible_zones_alphabetical_order() -> None:
    from collections import Counter

    walkable_counts: Counter = Counter({"zeta.zone": 6, "alpha.zone": 6, "mu.zone": 6})
    assert bam.select_eligible_zones(walkable_counts) == ["alpha.zone", "mu.zone", "zeta.zone"]


# ---------- load_walkability tolerance -------------------------------------


def test_load_walkability_empty_on_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bam, "WALK_PATH", tmp_path / "nope.json")
    # Pass the path explicitly so the test is robust regardless of whether
    # the default-arg binding trap avoidance is in effect or not.
    assert bam.load_walkability(tmp_path / "nope.json") == {}


def test_load_walkability_empty_on_malformed_logs_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(bam, "WALK_PATH", bad)
    # Pass path explicitly so the test is robust.
    assert bam.load_walkability(bad) == {}
    captured = capsys.readouterr()
    assert "WARN" in captured.err and "malformed" in captured.err


def test_load_walkability_empty_on_missing_classifications_key_logs_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    p = tmp_path / "no-key.json"
    p.write_text(json.dumps({"schema": "x", "summary": {}}), encoding="utf-8")
    monkeypatch.setattr(bam, "WALK_PATH", p)
    assert bam.load_walkability(p) == {}
    captured = capsys.readouterr()
    assert "WARN" in captured.err and "'classifications'" in captured.err


def test_load_walkability_happy_path() -> None:
    if not bam.WALK_PATH.exists():
        pytest.skip("real walkability-classification.json not present in this checkout")
    result = bam.load_walkability()
    assert isinstance(result, dict)
    assert len(result) > 0
    sample = next(iter(result.values()))
    assert isinstance(sample, str)


def test_run_step_timeout_returns_rc124(monkeypatch: pytest.MonkeyPatch) -> None:
    """subprocess.TimeoutExpired must yield rc=124 with the TIMEOUT marker in stderr."""

    def fake_run(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=args, timeout=0.001)

    monkeypatch.setattr(bam.subprocess, "run", fake_run)
    rc, stdout, stderr = bam._run_step(["python", "-c", "import time; time.sleep(2)"])
    assert rc == 124
    assert "[TIMEOUT after" in stderr
    assert bam._tail(stdout) == ""


# ---------- build_one_zone: per-stage mocks ---------------------------------


def _patch_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # REPO_ROOT is referenced by build_one_zone via obj_path.relative_to(REPO_ROOT)
    # so we mirror it to tmp_path here so the in-tmp_path zone layout is consistent.
    monkeypatch.setattr(bam, "PHASE6_DIR", tmp_path)
    monkeypatch.setattr(bam, "INDEX_PATH", tmp_path / "navmesh-index.json")
    monkeypatch.setattr(bam, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(bam, "ZONES_SUBDIR", "zones")


def test_build_one_zone_extract_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_paths(tmp_path, monkeypatch)
    zone = "ep1.world_objects.dungeons"
    walk: Counter[str] = Counter()
    total: Counter[str] = Counter({zone: 7})
    # Ship a Synthetic CompletedProcess with rc=1 -- extract says no.
    fake_proc = _make_completed_process(returncode=1, stderr="ERROR: zone has zero walkable assets", stdout="hello")
    monkeypatch.setattr(
        bam.subprocess,
        "run",
        MagicMock(return_value=fake_proc),
    )
    entry = bam.build_one_zone(
        zone,
        min_walkable=5,
        walkable_counts=walk,
        total_counts=total,
    )
    assert entry["status"] == "failed"
    assert entry["failure"]["stage"] == "extract"
    assert entry["failure"]["returncode"] == 1
    assert "walkable" in entry["failure"]["message"]
    assert entry["failure"]["stdout_tail"].endswith("hello")
    assert entry["failure"]["stderr_tail"].startswith("ERROR")


def test_build_one_zone_build_stage_failure_rc0_but_missing_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If extract rc=0 but OBJ is missing, fail at extract stage."""
    _patch_paths(tmp_path, monkeypatch)
    zone = "ep1.world_objects.dungeons"
    walk = Counter({zone: 6})
    total = Counter({zone: 6})
    fake_proc = _make_completed_process(returncode=0)
    monkeypatch.setattr(bam.subprocess, "run", MagicMock(return_value=fake_proc))
    entry = bam.build_one_zone(zone, min_walkable=5, walkable_counts=walk, total_counts=total)
    assert entry["status"] == "failed"
    assert entry["failure"]["stage"] == "extract"
    assert "OBJ missing" in entry["failure"]["message"]


def test_build_one_zone_build_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Extract succeeds (creates OBJ), build fails (rc!=0)."""
    _patch_paths(tmp_path, monkeypatch)
    zone = "ep1.world_objects.dungeons"
    walk = Counter({zone: 6})
    total = Counter({zone: 6})

    def fake_run(args, **_: Any) -> subprocess.CompletedProcess[str]:
        # Stage 1: extract -- print to disk and return rc=0
        if "extract_zone_geometry" in args[1]:
            obj_path = Path(args[args.index("--out") + 1])
            obj_path.parent.mkdir(parents=True, exist_ok=True)
            obj_path.write_text("# fake OBJ\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n", encoding="utf-8")
            meta_path = Path(args[args.index("--out-meta") + 1])
            meta_path.write_text("{}", encoding="utf-8")
            return _make_completed_process(returncode=0, stdout="extract OK", stderr="")
        # Stage 2: build -- fail
        if "build_navmesh" in args[1]:
            return _make_completed_process(returncode=2, stderr="ERROR: recast4j returned null result", stdout="")
        pytest.fail(f"unexpected subprocess call: {args[:5]}")

    monkeypatch.setattr(bam.subprocess, "run", fake_run)
    entry = bam.build_one_zone(zone, min_walkable=5, walkable_counts=walk, total_counts=total)
    assert entry["status"] == "failed"
    assert entry["failure"]["stage"] == "build"
    assert "recast4j" in entry["failure"]["message"]
    assert entry["failure"]["returncode"] == 2
    assert entry["obj_path"].endswith("input.obj")


def test_build_one_zone_validate_report_invalid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Extract + build succeed; validate_rc=0 but valid=False -> status='failed'."""
    _patch_paths(tmp_path, monkeypatch)
    zone = "ep1.world_objects.dungeons"
    walk = Counter({zone: 6})
    total = Counter({zone: 6})

    build_payload = {
        "success": True,
        "mesh": {"npolys": 9, "nverts": 30, "walkable_polys": 9, "nvp": 6},
        "bounds": {"bmin": [0.0, 0.0, 0.0], "bmax": [100.0, 50.0, 100.0]},
    }
    val_payload = {
        "valid": False,
        "checks": [
            {"check": "single_connected_component", "pass": True, "detail": "1 component"},
            {"check": "no_isolated_polys", "pass": False, "detail": "2 isolated polys"},
        ],
        "summary": {"isolated_polys": 2, "connected_components": 2, "max_edge_length": 12.3},
    }

    def fake_run(args, **_: Any) -> subprocess.CompletedProcess[str]:
        if "extract_zone_geometry" in args[1]:
            Path(args[args.index("--out") + 1]).write_text("# obj\n", encoding="utf-8")
            Path(args[args.index("--out-meta") + 1]).write_text("{}", encoding="utf-8")
            return _make_completed_process(returncode=0)
        if "build_navmesh" in args[1]:
            Path(args[args.index("--out") + 1]).write_text(json.dumps(build_payload), encoding="utf-8")
            return _make_completed_process(returncode=0)
        if "validate_navmesh" in args[1]:
            Path(args[args.index("--out") + 1]).write_text(json.dumps(val_payload), encoding="utf-8")
            return _make_completed_process(returncode=0)
        pytest.fail(f"unexpected subprocess call: {args[:5]}")

    monkeypatch.setattr(bam.subprocess, "run", fake_run)
    entry = bam.build_one_zone(zone, min_walkable=5, walkable_counts=walk, total_counts=total)
    assert entry["status"] == "failed"
    assert entry["failure"]["stage"] == "validate"
    assert "no_isolated_polys" in entry["failure"]["message"]
    assert entry["stats"]["poly_count"] == 9
    assert entry["stats"]["isolated_polys"] == 2


def test_build_one_zone_full_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """All three stages succeed with valid=True -> status='built' with stats+bounds."""
    _patch_paths(tmp_path, monkeypatch)
    zone = "ep1.world_objects.dungeons"
    walk = Counter({zone: 6})
    total = Counter({zone: 6})

    build_payload = {
        "success": True,
        "mesh": {"npolys": 9, "nverts": 30, "walkable_polys": 9, "nvp": 6},
        "bounds": {"bmin": [0.0, 0.0, 0.0], "bmax": [100.0, 50.0, 100.0]},
    }
    val_payload = {
        "valid": True,
        "checks": [{"check": "poly_count_gt_zero", "pass": True, "detail": "9 polys"}],
        "summary": {"isolated_polys": 0, "connected_components": 1, "max_edge_length": 10.0},
    }

    def fake_run(args, **_: Any) -> subprocess.CompletedProcess[str]:
        if "extract_zone_geometry" in args[1]:
            Path(args[args.index("--out") + 1]).write_text("# obj\n", encoding="utf-8")
            Path(args[args.index("--out-meta") + 1]).write_text("{}", encoding="utf-8")
            return _make_completed_process(returncode=0)
        if "build_navmesh" in args[1]:
            Path(args[args.index("--out") + 1]).write_text(json.dumps(build_payload), encoding="utf-8")
            return _make_completed_process(returncode=0)
        if "validate_navmesh" in args[1]:
            Path(args[args.index("--out") + 1]).write_text(json.dumps(val_payload), encoding="utf-8")
            return _make_completed_process(returncode=0)
        pytest.fail(f"unexpected subprocess call: {args[:5]}")

    monkeypatch.setattr(bam.subprocess, "run", fake_run)
    entry = bam.build_one_zone(zone, min_walkable=5, walkable_counts=walk, total_counts=total)
    assert entry["status"] == "built"
    assert "failure" not in entry  # failure key cleared on built
    assert entry["stats"]["poly_count"] == 9
    assert entry["stats"]["walkable_polys"] == 9
    assert entry["stats"]["isolated_polys"] == 0
    assert entry["stats"]["connected_components"] == 1
    assert entry["bounds"]["bmin"] == [0.0, 0.0, 0.0]
    assert entry["bounds"]["bmax"] == [100.0, 50.0, 100.0]
    assert entry["connected_zones"] == []  # M6.2 still empty
    assert entry["obj_path"].endswith("input.obj")
    assert entry["navmesh_json_path"].endswith("navmesh-build.json")
    assert entry["validation_path"].endswith("navmesh-validation.json")


# ---------- build_index_doc shape -------------------------------------------


def test_build_index_doc_alphabetical_zone_order() -> None:
    eligible = ["zeta.zone", "alpha.zone"]
    built = {
        "alpha.zone": {"status": "built", "slug": "alpha-zone"},
        "zeta.zone": {"status": "failed", "slug": "zeta-zone"},
    }
    from collections import Counter

    skipped: Counter = Counter({"beta.zone": 1})
    doc = bam.build_index_doc(eligible=eligible, skipped=skipped, built_entries=built, min_walkable=5)
    # Eligible zones are inserted first, then skipped zones appended
    # (NOT pure alphabetical across both groups).
    assert list(doc["zones"].keys()) == ["alpha.zone", "zeta.zone", "beta.zone"]
    assert doc["zones"]["alpha.zone"]["status"] == "built"
    assert doc["zones"]["beta.zone"]["status"] == "skipped"
    # walkable count = 1 > 0 → falls through to the default reason invented by
    # build_index_doc (no caller-supplied skipped_reasons dict).
    assert doc["zones"]["beta.zone"]["skip_reason"] == "low_walkable_count"
    assert doc["summary"]["eligible_zones"] == 2
    assert doc["summary"]["built_zones"] == 1
    assert doc["summary"]["failed_zones"] == 1
    assert doc["summary"]["skipped_zones"] == 1
    assert doc["summary"]["walkable_labels"] == sorted(bam.WALKABLE_LABELS)


def test_build_index_doc_all_skipped_zero_eligible() -> None:
    from collections import Counter

    doc = bam.build_index_doc(eligible=[], skipped=Counter({"a.zone": 0}), built_entries={}, min_walkable=5)
    assert doc["summary"]["eligible_zones"] == 0
    assert doc["summary"]["built_zones"] == 0
    assert doc["summary"]["failed_zones"] == 0
    assert doc["zones"]["a.zone"]["status"] == "skipped"
    assert doc["zones"]["a.zone"]["walkable_asset_count"] == 0
    assert doc["zones"]["a.zone"]["skip_reason"] == "no_walkable_assets"


# ---------- validate_against_schema ----------------------------------------


def test_validate_against_schema_passes_on_correct_index(tmp_path: Path) -> None:
    from collections import Counter

    idx = tmp_path / "navmesh-index.json"
    doc = bam.build_index_doc(
        eligible=["ep1.world_objects.dungeons"],
        skipped=Counter(),
        built_entries={
            "ep1.world_objects.dungeons": {
                "status": "built",
                "slug": "ep1-world_objects-dungeons",
                "walkable_asset_count": 12,
                "total_asset_count": 14,
                "obj_path": "Exports/navmesh-phase6/zones/ep1-world_objects-dungeons/input.obj",
                "navmesh_json_path": "Exports/navmesh-phase6/zones/ep1-world_objects-dungeons/navmesh-build.json",
                "validation_path": "Exports/navmesh-phase6/zones/ep1-world_objects-dungeons/navmesh-validation.json",
                "stats": {"poly_count": 9, "walkable_polys": 9, "vert_count": 30},
                "bounds": {"bmin": [0.0, 0.0, 0.0], "bmax": [100.0, 50.0, 100.0]},
                "connected_zones": [],
            }
        },
        min_walkable=5,
    )
    idx.write_text(json.dumps(doc), encoding="utf-8")
    assert bam._validate_against_schema(idx) == 0


def test_validate_against_schema_catches_walkable_labels_drift(tmp_path: Path) -> None:
    from collections import Counter

    idx = tmp_path / "navmesh-index.json"
    doc = bam.build_index_doc(eligible=[], skipped=Counter(), built_entries={}, min_walkable=5)
    # Replace walkable_labels with an invalid set.
    doc["summary"]["walkable_labels"] = ["unknown_label"]
    idx.write_text(json.dumps(doc), encoding="utf-8")
    assert bam._validate_against_schema(idx) == 1


def test_validate_against_schema_catches_bounds_inversion(tmp_path: Path) -> None:
    from collections import Counter

    idx = tmp_path / "navmesh-index.json"
    doc = bam.build_index_doc(
        eligible=["ep1.world_objects.dungeons"],
        skipped=Counter(),
        built_entries={
            "ep1.world_objects.dungeons": {
                "status": "built",
                "slug": "ep1-world_objects-dungeons",
                "walkable_asset_count": 5,
                "total_asset_count": 5,
                "stats": {"poly_count": 0, "walkable_polys": 0},
                "bounds": {"bmin": [200.0, 0.0, 0.0], "bmax": [10.0, 50.0, 100.0]},  # inverted
                "connected_zones": [],
            }
        },
        min_walkable=5,
    )
    idx.write_text(json.dumps(doc), encoding="utf-8")
    assert bam._validate_against_schema(idx) == 1


def test_validate_against_schema_catches_orphan_connected_zone(tmp_path: Path) -> None:
    from collections import Counter

    idx = tmp_path / "navmesh-index.json"
    doc = bam.build_index_doc(
        eligible=["ep1.world_objects.dungeons"],
        skipped=Counter(),
        built_entries={
            "ep1.world_objects.dungeons": {
                "status": "built",
                "slug": "ep1-world_objects-dungeons",
                "walkable_asset_count": 5,
                "total_asset_count": 5,
                "stats": {"poly_count": 0, "walkable_polys": 0},
                "connected_zones": ["never_heard_of_this"],  # not a sibling key
            }
        },
        min_walkable=5,
    )
    idx.write_text(json.dumps(doc), encoding="utf-8")
    assert bam._validate_against_schema(idx) == 1


def test_validate_against_schema_catches_bad_stage_enum(tmp_path: Path) -> None:
    from collections import Counter

    idx = tmp_path / "navmesh-index.json"
    doc = bam.build_index_doc(
        eligible=["ep1.world_objects.dungeons"],
        skipped=Counter(),
        built_entries={
            "ep1.world_objects.dungeons": {
                "status": "failed",
                "slug": "ep1-world_objects-dungeons",
                "walkable_asset_count": 5,
                "total_asset_count": 5,
                "connected_zones": [],
                "failure": {
                    "stage": "not_a_real_stage",
                    "message": "boom",
                },
            }
        },
        min_walkable=5,
    )
    idx.write_text(json.dumps(doc), encoding="utf-8")
    assert bam._validate_against_schema(idx) == 1


def test_validate_against_schema_catches_bad_skip_reason(tmp_path: Path) -> None:
    from collections import Counter

    idx = tmp_path / "navmesh-index.json"
    doc = bam.build_index_doc(
        eligible=[],
        skipped=Counter({"ep1.world_objects.dungeons": 1}),
        built_entries={},
        min_walkable=5,
    )
    # Override skip_reason with a non-enum value.
    doc["zones"]["ep1.world_objects.dungeons"]["skip_reason"] = "weather_too_bad"
    idx.write_text(json.dumps(doc), encoding="utf-8")
    assert bam._validate_against_schema(idx) == 1


# ---------- main(): end-to-end with mocked subprocess ------------------------


def test_main_run_writes_index_with_expected_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Build a synthetic environment
    fly_index_path = tmp_path / "flythrough-index.json"
    walk_path = tmp_path / "walk.json"
    zone = "ep1.world_objects.dungeons"
    fly = _synthetic_fly_index({zone: (7, 2)})
    fly_index_path.write_text(json.dumps(fly), encoding="utf-8")
    walk_payload = {
        "schema": "walkability-v1",
        "classifications": [{"asset_id": aid, "label": "walkable_structure"} for aid in list(fly["assets"].keys())[:7]]
        + [{"asset_id": aid, "label": "non_walkable_prop"} for aid in list(fly["assets"].keys())[7:]],
    }
    walk_path.write_text(json.dumps(walk_payload), encoding="utf-8")

    monkeypatch.setattr(bam, "FLY_INDEX", fly_index_path)
    monkeypatch.setattr(bam, "WALK_PATH", walk_path)
    monkeypatch.setattr(bam, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(bam, "PHASE6_DIR", tmp_path / "phase6")
    monkeypatch.setattr(bam, "INDEX_PATH", tmp_path / "phase6" / "navmesh-index.json")
    monkeypatch.setattr(bam, "SELECTED_INDEX_PATH", tmp_path / "phase6" / "navmesh-index.selected.json")

    build_payload = {
        "success": True,
        "mesh": {"npolys": 9, "nverts": 30, "walkable_polys": 9, "nvp": 6},
        "bounds": {"bmin": [0.0, 0.0, 0.0], "bmax": [100.0, 50.0, 100.0]},
    }
    val_payload = {
        "valid": True,
        "checks": [],
        "summary": {"isolated_polys": 0, "connected_components": 1, "max_edge_length": 12.0},
    }

    def fake_run(args, **_: Any) -> subprocess.CompletedProcess[str]:
        if "extract_zone_geometry" in args[1]:
            out_idx = args.index("--out")
            meta_idx = args.index("--out-meta")
            Path(args[out_idx + 1]).write_text("# obj\n", encoding="utf-8")
            Path(args[meta_idx + 1]).write_text("{}", encoding="utf-8")
            return _make_completed_process(returncode=0)
        if "build_navmesh" in args[1]:
            Path(args[args.index("--out") + 1]).write_text(json.dumps(build_payload), encoding="utf-8")
            return _make_completed_process(returncode=0)
        if "validate_navmesh" in args[1]:
            Path(args[args.index("--out") + 1]).write_text(json.dumps(val_payload), encoding="utf-8")
            return _make_completed_process(returncode=0)
        pytest.fail(f"unexpected subprocess call: {args[:5]}")

    monkeypatch.setattr(bam.subprocess, "run", fake_run)

    rc = bam.main(["run", "--zones", zone])
    assert rc == 0
    assert not bam.INDEX_PATH.exists(), "selected run must not overwrite the canonical index"
    written = json.loads(bam.SELECTED_INDEX_PATH.read_text())
    assert written["run"]["scope"] == "selected"
    assert written["schema_version"] == bam.SCHEMA_VERSION
    assert written["summary"]["eligible_zones"] == 1
    assert written["summary"]["built_zones"] == 1
    assert written["summary"]["failed_zones"] == 0
    assert written["zones"][zone]["status"] == "built"
    assert written["zones"][zone]["stats"]["poly_count"] == 9


def test_main_run_no_eligible_zones_writes_empty_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fly_index_path = tmp_path / "flythrough-index.json"
    walk_path = tmp_path / "walk.json"
    fly_index_path.write_text(
        json.dumps(_synthetic_fly_index({"ep1.world_objects.dungeons": (3, 0)})),
        encoding="utf-8",
    )
    walk_path.write_text(
        json.dumps(
            {
                "classifications": [
                    {"asset_id": k, "label": "walkable_structure"}
                    for k in list(_synthetic_fly_index({"ep1.world_objects.dungeons": (3, 0)})["assets"].keys())
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(bam, "FLY_INDEX", fly_index_path)
    monkeypatch.setattr(bam, "WALK_PATH", walk_path)
    monkeypatch.setattr(bam, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(bam, "PHASE6_DIR", tmp_path / "phase6")
    monkeypatch.setattr(bam, "INDEX_PATH", tmp_path / "phase6" / "navmesh-index.json")
    rc = bam.main(["run"])
    assert rc == 0
    written = json.loads((tmp_path / "phase6" / "navmesh-index.json").read_text())
    assert written["summary"]["eligible_zones"] == 0
    assert written["summary"]["built_zones"] == 0
    assert written["zones"]["ep1.world_objects.dungeons"]["status"] == "skipped"
    assert written["zones"]["ep1.world_objects.dungeons"]["skip_reason"] == "low_walkable_count"
    # Forward-compat: skipped entries carry total_asset_count from the index
    # so M6.2 can re-evaluate without re-running compute_zone_counts.
    assert written["zones"]["ep1.world_objects.dungeons"]["total_asset_count"] == 3


def test_main_run_with_unknown_zones_surfaces_them_as_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Passing --zones for zones not in flythrough-index must still be recorded
    in the index doc as 'skipped' with reason 'not_in_flythrough_index'."""
    fly_index_path = tmp_path / "flythrough-index.json"
    walk_path = tmp_path / "walk.json"
    known_zone = "ep1.world_objects.dungeons"
    fly_index_path.write_text(
        json.dumps(_synthetic_fly_index({known_zone: (3, 1)})),
        encoding="utf-8",
    )
    walk_path.write_text(
        json.dumps(
            {
                "classifications": [
                    {"asset_id": k, "label": "walkable_structure"}
                    for k in list(_synthetic_fly_index({known_zone: (3, 1)})["assets"].keys())
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(bam, "FLY_INDEX", fly_index_path)
    monkeypatch.setattr(bam, "WALK_PATH", walk_path)
    monkeypatch.setattr(bam, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(bam, "PHASE6_DIR", tmp_path / "phase6")
    monkeypatch.setattr(bam, "INDEX_PATH", tmp_path / "phase6" / "navmesh-index.json")
    unknown_zone = "ep9.never_seen_in_wild"
    rc = bam.main(["run", "--zones", known_zone, unknown_zone, "--out", str(bam.INDEX_PATH)])
    assert rc == 0
    written = json.loads((tmp_path / "phase6" / "navmesh-index.json").read_text())
    assert unknown_zone in written["zones"], "requested-but-missing zone must surface in index"
    assert written["zones"][unknown_zone]["status"] == "skipped"
    assert written["zones"][unknown_zone]["skip_reason"] == "not_in_flythrough_index"
    assert written["zones"][unknown_zone]["walkable_asset_count"] == 0


def test_main_status_returns_1_when_index_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bam, "INDEX_PATH", tmp_path / "does-not-exist.json")
    assert bam.main(["status"]) == 1


def test_status_returns_2_for_stale_source(tmp_path: Path) -> None:
    idx = tmp_path / "index.json"
    doc = bam.build_index_doc(eligible=[], skipped=Counter(), built_entries={}, min_walkable=5)
    doc["sources"]["flythrough_index"]["path"] = str(tmp_path / "missing.json")
    idx.write_text(json.dumps(doc), encoding="utf-8")
    assert bam._print_status(idx) == 2


def test_main_check_schema_returns_0_on_valid_on_disk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from collections import Counter

    idx = tmp_path / "navmesh-index.json"
    doc = bam.build_index_doc(
        eligible=["ep1.world_objects.dungeons"],
        skipped=Counter(),
        built_entries={
            "ep1.world_objects.dungeons": {
                "status": "built",
                "slug": "ep1-world_objects-dungeons",
                "walkable_asset_count": 5,
                "total_asset_count": 5,
                "connected_zones": [],
            }
        },
        min_walkable=5,
    )
    idx.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(bam, "INDEX_PATH", idx)
    assert bam.main(["check-schema"]) == 0
