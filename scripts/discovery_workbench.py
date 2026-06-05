#!/usr/bin/env python3
"""Aggregate RiftAssetDumper discovery reports into a ranked workbench.

This helper is intentionally read/report-only: the .NET RiftAssetDumper remains
the parser/source of truth, and Invoke-RiftAssetWorkflow.ps1 remains the workflow
runner. This script only reads generated JSON reports and writes derived
candidate-only JSON/Markdown under ignored Exports/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPORT_FILES = {
    "inventory": "nif-mesh-binding-inventory.json",
    "sibling_family": "position-source-sibling-family-report.json",
    "sibling_lead_guard": "position-source-sibling-lead-guard.json",
    "sibling_extra_position": "position-source-sibling-extra-position-report.json",
    "sibling_secondary": "position-source-sibling-secondary-probe-comparison.json",
    "residual_classifier": "residual-position-classifier-report.json",
    "residual_family": "residual-position-family-crosstab.json",
    "residual_review": "residual-target-family-review.json",
}


@dataclass(frozen=True)
class LoadedReport:
    key: str
    path: Path
    exists: bool
    data: dict[str, Any] | None
    mtime_utc: str | None
    sha256: str | None
    error: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build candidate-only discovery scoreboard and next-probe queue.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1]),
        help="RiftAssetDumper repo root, not Source/.",
    )
    parser.add_argument("--exports", default="", help="Generated report directory; defaults to <root>/Exports.")
    parser.add_argument("--top", type=int, default=20, help="Maximum candidates in Markdown scoreboard.")
    parser.add_argument("--queue-size", type=int, default=12, help="Maximum next-probe queue items.")
    parser.add_argument(
        "--privacy-scan", action="store_true", help="Fail if generated outputs contain local user-profile paths."
    )
    return parser.parse_args()


def utc_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json_report(key: str, path: Path) -> LoadedReport:
    if not path.exists():
        return LoadedReport(key, path, False, None, None, None, "missing")

    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            return LoadedReport(
                key, path, True, None, utc_from_timestamp(path.stat().st_mtime), sha256_file(path), "not a JSON object"
            )
        return LoadedReport(key, path, True, data, utc_from_timestamp(path.stat().st_mtime), sha256_file(path))
    except Exception as exc:  # noqa: BLE001 - report load failures as data, do not hide them.
        mtime = utc_from_timestamp(path.stat().st_mtime) if path.exists() else None
        sha = sha256_file(path) if path.exists() else None
        return LoadedReport(key, path, path.exists(), None, mtime, sha, str(exc))


def get_value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "-":
            return default
        return int(value)
    except TypeError, ValueError:
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "-":
            return default
        return float(value)
    except TypeError, ValueError:
        return default


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes"}
    return bool(value)


def clamp_score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def md_cell(value: Any) -> str:
    text = "-" if value is None or value == "" else str(value)
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def repo_command(repo_root: Path, mode: str, *extra: str) -> str:
    workflow = repo_root / "scripts" / "Invoke-RiftAssetWorkflow.ps1"
    args = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        f'"{workflow}"',
        "-Mode",
        mode,
        *extra,
    ]
    return " ".join(args)


def mesh_probe_command(repo_root: Path, asset_id: str, mesh_block: int | str) -> str:
    return repo_command(
        repo_root, "MeshProbe", "-Id", str(asset_id), "-MeshBlock", str(mesh_block), "-SkipBuild", "-PrivacyScan"
    )


def candidate(
    *,
    candidate_id: str,
    title: str,
    category: str,
    priority: str,
    score: int,
    rationale: str,
    evidence: list[str],
    commands: list[str] | None = None,
    mesh_size: int | None = None,
    stream: str | None = None,
    payload: int | None = None,
    guard_coverage: list[str] | None = None,
    attribute_set_status: str = "-",
    strict_classifier_pass: bool = False,
    known_noise: bool = False,
    exclusion: bool = False,
    source_reports: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "CandidateId": candidate_id,
        "CandidateOnly": True,
        "Title": title,
        "Category": category,
        "Priority": priority,
        "Score": score,
        "MeshSize": mesh_size,
        "Stream": stream,
        "Payload": payload,
        "StrictClassifierPass": strict_classifier_pass,
        "KnownNoise": known_noise,
        "Exclusion": exclusion,
        "AttributeSetStatus": attribute_set_status,
        "GuardCoverage": guard_coverage or [],
        "Evidence": evidence,
        "Rationale": rationale,
        "Commands": commands or [],
        "SourceReports": source_reports or [],
        "PromotionStatus": "candidate-only; no parser role, geometry truth, or OBJ/export readiness promoted",
    }


def parse_mesh_blocks(mesh_blocks: Any) -> list[int]:
    if isinstance(mesh_blocks, list):
        values = mesh_blocks
    else:
        values = re.findall(r"mesh#(\d+)", str(mesh_blocks))
    result: list[int] = []
    for value in values:
        if isinstance(value, int):
            result.append(value)
            continue
        match = re.search(r"(\d+)", str(value))
        if match:
            result.append(int(match.group(1)))
    return result


def first_list_item(value: Any) -> Any:
    if isinstance(value, list) and value:
        return value[0]
    return None


def representative_ids(value: Any, limit: int = 3) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value[:limit] if str(item)]
    return [item for item in re.split(r"[, ]+", str(value)) if item][:limit]


def build_residual_candidates(reports: dict[str, LoadedReport], repo_root: Path) -> list[dict[str, Any]]:
    classifier = reports["residual_classifier"].data or {}
    family = reports["residual_family"].data or {}
    rows = classifier.get("Rows") or []
    commands_by_payload: dict[int, str] = {}
    id_mesh_by_payload: dict[int, list[dict[str, Any]]] = {}

    for command_row in family.get("RepresentativeProbeCommands") or []:
        payload = as_int(command_row.get("Payload"))
        command = str(command_row.get("Command") or "")
        if payload and command:
            commands_by_payload[payload] = command

    for id_row in family.get("IdMeshPairs") or []:
        payload = as_int(id_row.get("Payload"))
        id_mesh_by_payload.setdefault(payload, []).append(id_row)

    result: list[dict[str, Any]] = []
    for row in rows:
        payload = as_int(row.get("Payload"))
        plausible = as_float(row.get("Plausible"))
        sample_count = as_int(row.get("SampleCount"))
        sample_meshes = str(row.get("SampleMeshes") or "")
        strict_pass = as_bool(row.get("StrictPass"))
        paired_bonus = 8 if "mesh#7" in sample_meshes and "mesh#27" in sample_meshes else 0
        priority_bonus = 0
        priority = "medium"
        if payload == 288:
            priority_bonus = 14
            priority = "highest"
        elif payload in {96, 180, 192, 396}:
            priority_bonus = 8
            priority = "high"
        elif plausible < 0.50:
            priority = "low"

        score = clamp_score(58 + plausible * 20 + sample_count + paired_bonus + priority_bonus)
        commands: list[str] = []
        if payload in commands_by_payload:
            commands.append(commands_by_payload[payload])
        paired_rows = [
            item for item in id_mesh_by_payload.get(payload, []) if str(item.get("PairStatus")) == "mesh#7+mesh#27"
        ]
        if paired_rows:
            id_prefix = str(paired_rows[0].get("IdPrefix"))
            commands.append(mesh_probe_command(repo_root, id_prefix, 7))
            commands.append(mesh_probe_command(repo_root, id_prefix, 27))

        known_noise = plausible < 0.50
        result.append(
            candidate(
                candidate_id=f"residual-305-stream188-payload{payload}",
                title=f"meshSize=305 stream@188 POSITION payload={payload}",
                category="residual-position",
                priority=priority,
                score=score if not known_noise else min(score, 25),
                mesh_size=305,
                stream=str(row.get("Stream") or "stream@188"),
                payload=payload,
                strict_classifier_pass=strict_pass,
                known_noise=known_noise,
                exclusion=False,
                attribute_set_status="residual family; compare mesh#7/mesh#27 sibling probes",
                guard_coverage=["ResidualPositionClassifierReport", "ResidualLeadGuard"],
                evidence=[
                    f"plausible={plausible:g}",
                    f"samples={sample_count}",
                    f"meshes={sample_meshes or '-'}",
                    f"strictPass={strict_pass}",
                    f"miss={row.get('MissReasons') or '-'}",
                ],
                rationale=(
                    "Best current residual-position lane; rank for follow-up "
                    "without lowering strict classifier thresholds."
                ),
                commands=commands,
                source_reports=["residual-position-classifier-report.json", "residual-position-family-crosstab.json"],
            )
        )
    return result


def build_sibling_family_candidates(reports: dict[str, LoadedReport], repo_root: Path) -> list[dict[str, Any]]:
    report = reports["sibling_family"].data or {}
    families = report.get("Families") or []
    result: list[dict[str, Any]] = []
    for fam in families:
        mesh_size = as_int(fam.get("MeshSize"))
        mesh_blocks = parse_mesh_blocks(fam.get("MeshBlocks"))
        offsets = str(fam.get("MeshPayloadOffsets") or "")
        groups = as_int(fam.get("EvidenceGroups"))
        links = as_int(fam.get("TotalStreamLinks"))
        target_blocks = str(fam.get("TargetBlocks") or "")
        title = f"meshSize={mesh_size} {fam.get('MeshBlocks')} {offsets}"
        priority = "medium"
        score = clamp_score(40 + groups * 1.5 + links * 0.5)
        if mesh_size == 329 and mesh_blocks == [7, 34]:
            priority = "high"
            # Strongest sibling-family lane, but keep it below the explicitly
            # prioritized meshSize=305 residual payload cluster. This workbench
            # ranks next discovery value only and must not let repetition alone
            # outrank the current residual-plausibility lead.
            score = min(max(score, 88), 90)
        elif mesh_size == 305 and mesh_blocks == [7, 27]:
            priority = "high"
            score = max(score, 82)
        elif mesh_size == 321 and mesh_blocks == [7, 31]:
            priority = "medium"
            score = max(score, 76)
        elif mesh_size == 325:
            priority = "deprioritized"
            score = 30

        reps = representative_ids(fam.get("RepresentativeIds"), 2)
        commands = [repo_command(repo_root, "PositionSourceSiblingFamilyReport", "-SkipBuild", "-PrivacyScan")]
        for rep in reps[:1]:
            for block in mesh_blocks[:2]:
                commands.append(mesh_probe_command(repo_root, rep, block))

        sid_candidate = f"sibling-family-{mesh_size}-{'-'.join(str(b) for b in mesh_blocks)}-{re.sub(r'[^0-9]+', '-', offsets).strip('-')}"
        result.append(
            candidate(
                candidate_id=sid_candidate,
                title=title,
                category="position-source-sibling-family",
                priority=priority,
                score=score,
                mesh_size=mesh_size,
                stream=offsets,
                payload=None,
                attribute_set_status="family-level only; inspect focused probes before any inference",
                guard_coverage=["PositionSourceSiblingFamilyReport", "PositionSourceSiblingLeadGuard"],
                evidence=[
                    f"groups={groups}",
                    f"links={links}",
                    f"targetBlocks={target_blocks}",
                    f"payloads={fam.get('PayloadBytes') or '-'}",
                    f"representatives={', '.join(reps) or '-'}",
                ],
                rationale=str(
                    fam.get("Decision") or "Repeated source-binding family; candidate-only ranking evidence."
                ),
                commands=commands,
                source_reports=["position-source-sibling-family-report.json"],
            )
        )
    return result


def build_extra_position_candidate(reports: dict[str, LoadedReport], repo_root: Path) -> list[dict[str, Any]]:
    report = reports["sibling_extra_position"].data or {}
    pairs = report.get("PairSummaries") or []
    if not pairs:
        return []
    ids = [str(row.get("Id")) for row in pairs if row.get("Id")]

    def _extract_payload(row: dict[str, Any]) -> str | None:
        match = re.search(r"payload=(\d+)", str(row.get("Mesh34ExtraPosition") or ""))
        return match.group(1) if match else None

    payloads = [p for row in pairs if (p := _extract_payload(row)) is not None]
    commands = [repo_command(repo_root, "PositionSourceSiblingExtraPositionReport", "-SkipBuild", "-PrivacyScan")]
    for asset_id in ids[:2]:
        commands.append(mesh_probe_command(repo_root, asset_id, 7))
        commands.append(mesh_probe_command(repo_root, asset_id, 34))

    return [
        candidate(
            candidate_id="sibling-extra-329-mesh34-304-57",
            title="meshSize=329 mesh#34 extra position-like @304/#57",
            category="position-source-sibling-extra",
            priority="high",
            score=84,
            mesh_size=329,
            stream="@304/#57",
            attribute_set_status="mesh#7 has full attr set; mesh#34 has no full attr set in guarded rows",
            guard_coverage=["PositionSourceSiblingExtraPositionReport"],
            evidence=[
                f"ids={', '.join(ids)}",
                f"mesh34ExtraPayloads={', '.join(payloads)}",
                "sharedPrimaryPosition=block#28 offsets=@212/@212",
            ],
            rationale=(
                "Repeated mesh#34 extra position-like stream is a "
                "source-binding clue only; keep separate from residual evidence."
            ),
            commands=commands,
            source_reports=["position-source-sibling-extra-position-report.json"],
        )
    ]


def build_secondary_candidates(reports: dict[str, LoadedReport], repo_root: Path) -> list[dict[str, Any]]:
    report = reports["sibling_secondary"].data or {}
    result: list[dict[str, Any]] = []
    for row in report.get("PairSummaries") or []:
        label = str(row.get("PairLabel") or "")
        asset_id = str(row.get("Id") or "")
        mesh_sizes = str(row.get("MeshSizes") or "")
        mesh_blocks = parse_mesh_blocks(row.get("MeshBlocks"))
        mesh_size = as_int(mesh_sizes.split(",")[0] if mesh_sizes else 0)
        score = 62
        if mesh_size == 321:
            score = 72
        elif mesh_size == 305:
            score = 70
        elif mesh_size == 329:
            score = 74

        commands = [repo_command(repo_root, "PositionSourceSiblingSecondaryProbeReport", "-SkipBuild", "-PrivacyScan")]
        for block in mesh_blocks[:2]:
            commands.append(mesh_probe_command(repo_root, asset_id, block))
        result.append(
            candidate(
                candidate_id=f"secondary-sibling-{asset_id}",
                title=label,
                category="secondary-sibling-spot-check",
                priority="medium",
                score=score,
                mesh_size=mesh_size,
                stream=str(row.get("SharedPositionStreams") or ""),
                attribute_set_status=str(row.get("AttributeSetCounts") or "-"),
                guard_coverage=["PositionSourceSiblingSecondaryProbeReport"],
                evidence=[
                    f"id={asset_id}",
                    f"meshes={row.get('MeshBlocks') or '-'}",
                    f"attributeSets={row.get('AttributeSetCounts') or '-'}",
                    f"shared={row.get('SharedPositionStreams') or '-'}",
                ],
                rationale=str(row.get("Decision") or "Secondary spot-check remains candidate-only."),
                commands=commands,
                source_reports=["position-source-sibling-secondary-probe-comparison.json"],
            )
        )
    return result


def build_noise_candidates(reports: dict[str, LoadedReport], repo_root: Path) -> list[dict[str, Any]]:
    report = reports["residual_review"].data or {}
    result: list[dict[str, Any]] = []
    for row in report.get("Rows") or []:
        label = str(row.get("Label") or "")
        decision = str(row.get("Decision") or "")
        mesh_size = as_int(row.get("MeshSize"))
        stream = str(row.get("Stream") or "")
        payload = as_int(row.get("Payload"))
        is_noise = bool(re.search(r"noise|side|color|low-signal|deprior", f"{label} {decision}", flags=re.IGNORECASE))
        is_325 = mesh_size == 325
        score = 12 if is_noise else 35
        if is_325:
            score = 20
        result.append(
            candidate(
                candidate_id=f"residual-review-{mesh_size}-{stream}-payload{payload}",
                title=f"meshSize={mesh_size} {stream} payload={payload} {label}".strip(),
                category="residual-review",
                priority="exclude" if is_noise else "review",
                score=score,
                mesh_size=mesh_size,
                stream=stream,
                payload=payload,
                known_noise=is_noise,
                exclusion=is_noise,
                attribute_set_status="not a promotion lane",
                guard_coverage=["ResidualLeadGuard"],
                evidence=[str(row.get("Evidence") or "-")],
                rationale=decision or "Residual-family review row.",
                commands=[repo_command(repo_root, "ResidualLeadGuard", "-SkipBuild", "-PrivacyScan")],
                source_reports=["residual-target-family-review.json"],
            )
        )
    return result


def build_topology_candidates(reports: dict[str, LoadedReport], repo_root: Path) -> list[dict[str, Any]]:
    inventory = reports["inventory"].data or {}
    fitness_rows = inventory.get("TopAttributeExtraMappingFitness") or []
    if not fitness_rows:
        return []
    row = fitness_rows[0]
    mesh_size = as_int(row.get("MeshSize"))
    extra_offset = as_int(row.get("ExtraMeshPayloadOffset"))
    vertex_count = as_int(row.get("VertexCount"))
    return [
        candidate(
            candidate_id=f"topology-proof-{mesh_size}-extra{extra_offset}-v{vertex_count}",
            title=f"meshSize={mesh_size} extra@{extra_offset} topology proof lane",
            category="topology-proof-guard",
            priority="guarded-baseline",
            score=45,
            mesh_size=mesh_size,
            stream=f"extra@{extra_offset}",
            payload=as_int(row.get("ExtraDeclaredPayloadBytes")),
            attribute_set_status="guarded topology proof lane; do not mix with residual promotion",
            guard_coverage=["AttributeExtraProofGuard", "AttributeExtraSiblingProofGuard"],
            evidence=[
                f"topology={row.get('Topology')}",
                f"vertexCount={vertex_count}",
                f"rawZeroBasedWins={row.get('RawZeroBasedPreferredCount')}",
                f"subtractOneWins={row.get('SubtractOnePreferredCount')}",
            ],
            rationale="Keep this as a protected proof baseline while position-source discovery continues.",
            commands=[
                repo_command(repo_root, "AttributeExtraProofGuard", "-SkipBuild", "-PrivacyScan"),
                repo_command(repo_root, "AttributeExtraSiblingProofGuard", "-SkipBuild", "-PrivacyScan"),
            ],
            source_reports=["nif-mesh-binding-inventory.json"],
        )
    ]


def build_freshness(reports: dict[str, LoadedReport]) -> list[dict[str, Any]]:
    inventory = reports.get("inventory")
    inventory_mtime = (
        inventory.path.stat().st_mtime if inventory and inventory.exists and inventory.path.exists() else None
    )
    rows: list[dict[str, Any]] = []
    for report in reports.values():
        stale = False
        if inventory_mtime is not None and report.key != "inventory" and report.exists and report.path.exists():
            stale = report.path.stat().st_mtime < inventory_mtime
        rows.append(
            {
                "Key": report.key,
                "Path": str(report.path),
                "Exists": report.exists,
                "MTimeUtc": report.mtime_utc,
                "Sha256": report.sha256,
                "Error": report.error,
                "OlderThanInventory": stale,
            }
        )
    return rows


def build_scoreboard(reports: dict[str, LoadedReport], repo_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(build_residual_candidates(reports, repo_root))
    rows.extend(build_sibling_family_candidates(reports, repo_root))
    rows.extend(build_extra_position_candidate(reports, repo_root))
    rows.extend(build_secondary_candidates(reports, repo_root))
    rows.extend(build_noise_candidates(reports, repo_root))
    rows.extend(build_topology_candidates(reports, repo_root))

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in rows:
        cid = str(row["CandidateId"])
        if cid in seen:
            continue
        seen.add(cid)
        unique.append(row)

    unique.sort(key=lambda item: (-as_int(item.get("Score")), str(item.get("CandidateId"))))
    for index, row in enumerate(unique, start=1):
        row["Rank"] = index
    return unique


def build_cross_checks(scoreboard: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Summarize boundaries between high-value lanes without promoting truth."""

    residual_305 = [
        row
        for row in scoreboard
        if row.get("Category") == "residual-position"
        and as_int(row.get("MeshSize")) == 305
        and str(row.get("Stream") or "") == "stream@188"
        and not as_bool(row.get("KnownNoise"))
    ]
    sibling_305 = next(
        (
            row
            for row in scoreboard
            if row.get("Category") == "position-source-sibling-family"
            and as_int(row.get("MeshSize")) == 305
            and "stream@188" in str(row.get("Stream") or "")
        ),
        None,
    )
    extra_329 = next(
        (row for row in scoreboard if row.get("CandidateId") == "sibling-extra-329-mesh34-304-57"),
        None,
    )

    checks: list[dict[str, Any]] = []
    if residual_305:
        top = residual_305[0]
        checks.append(
            {
                "CheckId": "mesh305-residual-vs-sibling-family",
                "CandidateOnly": True,
                "Decision": (
                    "Probe the highest-ranked meshSize=305 residual payload before "
                    "moving to another family; compare results against the "
                    "#7/#27 sibling-family surface, but do not merge the evidence lanes."
                ),
                "TopResidualCandidateId": top.get("CandidateId"),
                "TopResidualPayload": top.get("Payload"),
                "ResidualPayloadsByScore": [
                    {
                        "Payload": row.get("Payload"),
                        "Score": row.get("Score"),
                        "StrictClassifierPass": row.get("StrictClassifierPass"),
                    }
                    for row in residual_305[:5]
                ],
                "SiblingFamilyCandidateId": sibling_305.get("CandidateId") if sibling_305 else None,
                "SiblingFamilyEvidence": sibling_305.get("Evidence") if sibling_305 else [],
                "Guardrail": (
                    "Residual stream plausibility and TopPositionSourceSiblings "
                    "repetition answer different questions; require focused "
                    "mesh probes plus normal/UV/topology/proof agreement before "
                    "promotion."
                ),
                "SourceReports": [
                    "residual-position-classifier-report.json",
                    "residual-position-family-crosstab.json",
                    "position-source-sibling-family-report.json",
                ],
            }
        )

    if extra_329:
        checks.append(
            {
                "CheckId": "mesh329-extra-position-boundary",
                "CandidateOnly": True,
                "Decision": (
                    "Keep meshSize=329 mesh#34 @304/#57 as source-binding "
                    "search evidence only; do not combine it with "
                    "residual-position evidence or exporter readiness."
                ),
                "CandidateId": extra_329.get("CandidateId"),
                "Evidence": extra_329.get("Evidence"),
                "Guardrail": "mesh#34 lacks a complete attribute-set binding in guarded rows.",
                "SourceReports": ["position-source-sibling-extra-position-report.json"],
            }
        )

    checks.append(
        {
            "CheckId": "export-promotion-block",
            "CandidateOnly": True,
            "Decision": "OBJ/export remains blocked.",
            "Guardrail": (
                "Position, topology/index, normal/UV, bounds, repeated-family "
                "evidence, and proof guards must all agree before exporter promotion."
            ),
            "SourceReports": [],
        }
    )
    return checks


def build_probe_queue(scoreboard: list[dict[str, Any]], queue_size: int) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for row in scoreboard:
        if as_bool(row.get("KnownNoise")) or as_bool(row.get("Exclusion")):
            continue
        commands = [cmd for cmd in row.get("Commands", []) if cmd]
        if not commands:
            continue
        queue.append(
            {
                "QueueRank": len(queue) + 1,
                "CandidateId": row["CandidateId"],
                "CandidateOnly": True,
                "Score": row["Score"],
                "Title": row["Title"],
                "Rationale": row["Rationale"],
                "Commands": commands,
            }
        )
        if len(queue) >= queue_size:
            break
    return queue


def write_scoreboard_markdown(
    path: Path,
    scoreboard: list[dict[str, Any]],
    freshness: list[dict[str, Any]],
    cross_checks: list[dict[str, Any]],
    top: int,
) -> None:
    lines = [
        "# Discovery Workbench Scoreboard",
        "",
        (
            "Candidate-only ranked discovery view. This file is generated "
            "under ignored `Exports/`; do not stage generated discovery output."
        ),
        "",
        "| Rank | Score | Priority | Category | Candidate | Mesh | Stream | Payload | Noise | Evidence |",
        "|---:|---:|---|---|---|---:|---|---:|---|---|",
    ]
    for row in scoreboard[:top]:
        evidence = "; ".join(str(item) for item in row.get("Evidence", [])[:3])
        lines.append(
            "| {rank} | {score} | {priority} | {category} | {title} | {mesh} | "
            "{stream} | {payload} | {noise} | {evidence} |".format(
                rank=row["Rank"],
                score=row["Score"],
                priority=md_cell(row["Priority"]),
                category=md_cell(row["Category"]),
                title=md_cell(row["Title"]),
                mesh=md_cell(row.get("MeshSize")),
                stream=md_cell(row.get("Stream")),
                payload=md_cell(row.get("Payload")),
                noise=md_cell(row.get("KnownNoise")),
                evidence=md_cell(evidence),
            )
        )

    lines += [
        "",
        "## Cross-checks",
        "",
        (
            "These guardrails keep residual-position evidence, sibling "
            "source-binding evidence, and export readiness separate."
        ),
        "",
        "| Check | Decision | Guardrail |",
        "|---|---|---|",
    ]
    for row in cross_checks:
        lines.append(
            "| {check} | {decision} | {guardrail} |".format(
                check=md_cell(row.get("CheckId")),
                decision=md_cell(row.get("Decision")),
                guardrail=md_cell(row.get("Guardrail")),
            )
        )

    stale = [row for row in freshness if row.get("OlderThanInventory")]
    lines += [
        "",
        "## Freshness",
        "",
        f"- Reports loaded: `{sum(1 for row in freshness if row.get('Exists'))}/{len(freshness)}`.",
        f"- Reports older than current inventory: `{len(stale)}`.",
        "",
        "## Interpretation",
        "",
        "- Scores rank next discovery value only.",
        "- `CandidateOnly` is true for every row.",
        "- No parser role, geometry truth, or OBJ/export readiness is promoted by this helper.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_queue_markdown(path: Path, queue: list[dict[str, Any]]) -> None:
    lines = [
        "# Discovery Next Probe Queue",
        "",
        "Ready-to-run candidate-only probe commands generated from the workbench scoreboard.",
        "",
    ]
    for item in queue:
        lines += [
            f"## {item['QueueRank']}. {item['Title']}",
            "",
            f"- Candidate: `{item['CandidateId']}`",
            f"- Score: `{item['Score']}`",
            f"- Rationale: {item['Rationale']}",
            "- CandidateOnly: `true`",
            "",
        ]
        for command in item.get("Commands", []):
            lines += ["```powershell", command, "```", ""]
    lines.append("Do not treat queued probes as geometry/export truth; they are search actions only.")
    path.write_text("\n".join(lines), encoding="utf-8")


def privacy_scan(paths: list[Path]) -> None:
    user_profile_pattern = "C:" + "\\Users\\"
    local_account_pattern = "mr" + "koo"
    patterns = [
        re.compile(re.escape(user_profile_pattern), re.IGNORECASE),
        re.compile(rf"\b{re.escape(local_account_pattern)}\b", re.IGNORECASE),
    ]
    findings: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if any(pattern.search(line) for pattern in patterns):
                findings.append(f"{path}:{lineno}: {line.strip()}")
    if findings:
        joined = "\n".join(findings[:20])
        raise RuntimeError(
            f"Privacy scan failed: generated outputs contain local user-profile/account fragments:\n{joined}"
        )


def main() -> int:
    args = parse_args()
    repo_root = Path(args.root).resolve()
    exports = Path(args.exports).resolve() if args.exports else repo_root / "Exports"
    exports.mkdir(parents=True, exist_ok=True)

    reports = {key: load_json_report(key, exports / filename) for key, filename in REPORT_FILES.items()}
    scoreboard = build_scoreboard(reports, repo_root)
    queue = build_probe_queue(scoreboard, args.queue_size)
    freshness = build_freshness(reports)
    cross_checks = build_cross_checks(scoreboard)

    scoreboard_json = exports / "discovery-workbench-scoreboard.json"
    scoreboard_md = exports / "discovery-workbench-scoreboard.md"
    queue_json = exports / "discovery-next-probe-queue.json"
    queue_md = exports / "discovery-next-probe-queue.md"

    generated_at = datetime.now(UTC).isoformat()
    scoreboard_payload = {
        "Schema": "discovery-workbench-scoreboard/v1",
        "CandidateOnly": True,
        "GeneratedAtUtc": generated_at,
        "RepoRoot": str(repo_root),
        "ExportsDirectory": str(exports),
        "Inputs": freshness,
        "Candidates": scoreboard,
        "CrossChecks": cross_checks,
        "Interpretation": (
            "Ranked discovery workbench only; no parser role, geometry truth, or OBJ/export readiness is promoted."
        ),
    }
    queue_payload = {
        "Schema": "discovery-next-probe-queue/v1",
        "CandidateOnly": True,
        "GeneratedAtUtc": generated_at,
        "SourceScoreboard": str(scoreboard_json),
        "Queue": queue,
        "Interpretation": (
            "Commands are candidate-only discovery actions. Review generated "
            "outputs and guards before drawing conclusions."
        ),
    }

    scoreboard_json.write_text(json.dumps(scoreboard_payload, indent=2), encoding="utf-8")
    queue_json.write_text(json.dumps(queue_payload, indent=2), encoding="utf-8")
    write_scoreboard_markdown(scoreboard_md, scoreboard, freshness, cross_checks, args.top)
    write_queue_markdown(queue_md, queue)

    if args.privacy_scan:
        privacy_scan([scoreboard_json, scoreboard_md, queue_json, queue_md])

    print("Discovery Workbench completed.")
    print(f"Candidates: {len(scoreboard)}")
    print(f"Queued probe items: {len(queue)}")
    print(f"Scoreboard JSON: {scoreboard_json}")
    print(f"Scoreboard markdown: {scoreboard_md}")
    print(f"Queue JSON: {queue_json}")
    print(f"Queue markdown: {queue_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
