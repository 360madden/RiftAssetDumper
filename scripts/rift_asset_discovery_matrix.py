#!/usr/bin/env python3
"""Batch safe RiftAssetDumper discovery jobs and summarize their JSON output.

The .NET RiftAssetDumper remains the parser/source of truth. This Python helper
only orchestrates bounded jobs, validates/merges JSON reports, enforces
timeouts, and writes generated summaries under ignored Exports/.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = Path("C:/Program Files (x86)/Glyph/Games/RIFT/Live")
DEFAULT_SOLUTION = REPO_ROOT / "RiftAssetDumper.slnx"
DEFAULT_PROJECT = REPO_ROOT / "src" / "RiftAssetDumper" / "RiftAssetDumper.csproj"
DEFAULT_OUT = REPO_ROOT / "Exports" / "discovery-matrix"
SEMANTIC_SCHEMA = REPO_ROOT / "docs" / "schemas" / "asset-semantic-index-v1.schema.json"


@dataclass(frozen=True)
class DiscoveryJob:
    name: str
    command: str
    max_total: int
    type_filter: str = ""
    semantic_categories: tuple[str, ...] = ()
    limit: int = 100
    timeout_seconds: int = 120
    output: str = ""


@dataclass
class DiscoveryResult:
    name: str
    command: str
    arguments: list[str]
    output_path: str
    max_total: int
    type_filter: str
    semantic_categories: list[str]
    timeout_seconds: int
    duration_seconds: float
    exit_code: int
    timed_out: bool
    parsed_report: bool
    schema_version: str | None = None
    inspected_payloads: int | None = None
    failed: int | None = None
    entry_count: int = 0
    signature_group_count: int = 0
    type_counts: list[dict[str, Any]] = field(default_factory=list)
    semantic_category_counts: list[dict[str, Any]] = field(default_factory=list)
    xml_parse_status_counts: list[dict[str, Any]] = field(default_factory=list)
    xml_parse_warning_counts: list[dict[str, Any]] = field(default_factory=list)
    schema_valid: bool | None = None
    error_summary: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a bounded matrix of safe Rift asset discovery jobs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Copied RIFT Source directory.")
    parser.add_argument("--solution", default=str(DEFAULT_SOLUTION), help="Solution to build.")
    parser.add_argument("--project", default=str(DEFAULT_PROJECT), help="RiftAssetDumper project path.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Generated output directory.")
    parser.add_argument("--matrix", default="", help="Optional JSON matrix config path.")
    parser.add_argument("--configuration", default="Debug", help="Build configuration.")
    parser.add_argument("--framework", default="net9.0", help="Target framework.")
    parser.add_argument("--max-total", type=int, default=1000, help="Default max payloads for semantic jobs.")
    parser.add_argument("--xml-max-total", type=int, default=200, help="Max payloads for XML jobs.")
    parser.add_argument("--nif-max-total", type=int, default=500, help="Max payloads for NIF jobs.")
    parser.add_argument("--signature-max-total", type=int, default=500, help="Max payloads for signature baseline.")
    parser.add_argument("--limit", type=int, default=100, help="Per-report grouping/sample limit.")
    parser.add_argument("--timeout-seconds", type=int, default=120, help="Timeout per matrix job.")
    parser.add_argument("--skip-build", action="store_true", help="Use existing built executable.")
    parser.add_argument("--allow-failures", action="store_true", help="Write summary even if jobs fail.")
    parser.add_argument("--privacy-scan", action="store_true", help="Run tracked-file local path/account scan.")
    parser.add_argument("--no-schema-validate", action="store_true", help="Skip optional jsonschema validation.")
    parser.add_argument("--jobs", nargs="*", default=(), help="Optional subset of job names to run.")
    return parser.parse_args()


def safe_file_name(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-").lower()
    return safe or "job"


def default_jobs(args: argparse.Namespace) -> list[DiscoveryJob]:
    return [
        DiscoveryJob(
            "signature-baseline",
            "inventory-asset-signatures",
            args.signature_max_total,
            limit=args.limit,
            timeout_seconds=args.timeout_seconds,
        ),
        DiscoveryJob(
            "semantic-xml-map-zone",
            "build-asset-semantic-index",
            args.xml_max_total,
            "xml",
            ("hint:map-zone",),
            args.limit,
            args.timeout_seconds,
        ),
        DiscoveryJob(
            "semantic-xml-ui",
            "build-asset-semantic-index",
            args.xml_max_total,
            "xml",
            ("hint:ui",),
            args.limit,
            args.timeout_seconds,
        ),
        DiscoveryJob(
            "semantic-xml-actor-object",
            "build-asset-semantic-index",
            args.xml_max_total,
            "xml",
            ("hint:actor-object",),
            args.limit,
            args.timeout_seconds,
        ),
        DiscoveryJob(
            "semantic-lua",
            "build-asset-semantic-index",
            args.max_total,
            "lua",
            limit=args.limit,
            timeout_seconds=args.timeout_seconds,
        ),
        DiscoveryJob(
            "semantic-txt",
            "build-asset-semantic-index",
            args.max_total,
            "txt",
            limit=args.limit,
            timeout_seconds=args.timeout_seconds,
        ),
        DiscoveryJob(
            "signature-riff-audio",
            "inventory-asset-signatures",
            args.max_total,
            "riff",
            limit=args.limit,
            timeout_seconds=args.timeout_seconds,
        ),
        DiscoveryJob(
            "semantic-bin-waypoint-poi",
            "build-asset-semantic-index",
            args.max_total,
            "bin",
            ("hint:waypoint-poi",),
            args.limit,
            args.timeout_seconds,
        ),
        DiscoveryJob(
            "semantic-bin-quest-objective",
            "build-asset-semantic-index",
            args.max_total,
            "bin",
            ("hint:quest-objective",),
            args.limit,
            args.timeout_seconds,
        ),
        DiscoveryJob(
            "semantic-bin-map-zone",
            "build-asset-semantic-index",
            args.max_total,
            "bin",
            ("hint:map-zone",),
            args.limit,
            args.timeout_seconds,
        ),
        DiscoveryJob(
            "semantic-bin-actor-object",
            "build-asset-semantic-index",
            args.max_total,
            "bin",
            ("hint:actor-object",),
            args.limit,
            args.timeout_seconds,
        ),
        DiscoveryJob(
            "semantic-nif-texture-refs",
            "build-asset-semantic-index",
            args.nif_max_total,
            "nif",
            ("ref:texture",),
            args.limit,
            args.timeout_seconds,
        ),
        DiscoveryJob(
            "semantic-nif-model-refs",
            "build-asset-semantic-index",
            args.nif_max_total,
            "nif",
            ("ref:model",),
            args.limit,
            args.timeout_seconds,
        ),
    ]


def load_matrix_jobs(args: argparse.Namespace) -> list[DiscoveryJob]:
    if not args.matrix:
        jobs = default_jobs(args)
    else:
        matrix_path = Path(args.matrix)
        data = json.loads(matrix_path.read_text(encoding="utf-8-sig"))
        raw_jobs = data.get("Jobs", data) if isinstance(data, dict) else data
        if not isinstance(raw_jobs, list):
            raise ValueError("Matrix JSON must be a list or object with Jobs list.")
        jobs = []
        for raw in raw_jobs:
            if not isinstance(raw, dict):
                raise ValueError("Each matrix job must be an object.")
            name = str(raw.get("Name", "")).strip()
            command = str(raw.get("Command", "")).strip()
            if not name or not command:
                raise ValueError("Each matrix job requires Name and Command.")
            categories = raw.get("SemanticCategories", ())
            if isinstance(categories, str):
                categories = [categories]
            jobs.append(
                DiscoveryJob(
                    name=name,
                    command=command,
                    max_total=int(raw.get("MaxTotal", args.max_total)),
                    type_filter=str(raw.get("Type", "")),
                    semantic_categories=tuple(str(c) for c in categories),
                    limit=int(raw.get("Limit", args.limit)),
                    timeout_seconds=int(raw.get("TimeoutSeconds", args.timeout_seconds)),
                    output=str(raw.get("Output", "")),
                )
            )

    if args.jobs:
        wanted = {name.lower() for name in args.jobs}
        jobs = [job for job in jobs if job.name.lower() in wanted]
        missing = wanted - {job.name.lower() for job in jobs}
        if missing:
            raise ValueError(f"Unknown matrix job(s): {', '.join(sorted(missing))}")

    if not jobs:
        raise ValueError("Discovery matrix has no jobs.")
    for job in jobs:
        validate_job(job)
    return jobs


def validate_job(job: DiscoveryJob) -> None:
    allowed = {"inventory-asset-signatures", "build-asset-semantic-index"}
    if job.command not in allowed:
        raise ValueError(f"Job {job.name!r} uses unsupported command {job.command!r}.")
    if job.max_total < 0:
        raise ValueError(f"Job {job.name!r} has negative max_total.")
    if job.timeout_seconds <= 0:
        raise ValueError(f"Job {job.name!r} must have a positive timeout.")
    if "hint:*" in job.semantic_categories and job.max_total <= 0:
        raise ValueError(f"Job {job.name!r} uses hint:* and must be bounded with max_total.")


def build_tool(args: argparse.Namespace) -> Path:
    solution = Path(args.solution).resolve()
    project = Path(args.project).resolve()
    if not args.skip_build:
        print("==> build")
        run = subprocess.run(["dotnet", "build", str(solution), "--nologo"], text=True)
        if run.returncode != 0:
            raise RuntimeError(f"Build failed with exit code {run.returncode}.")
    tool_path = project.parent / "bin" / str(args.configuration) / str(args.framework) / "RiftAssetDumper.exe"
    if not tool_path.exists():
        raise FileNotFoundError(
            f"Built tool not found at {tool_path}; run without --skip-build or adjust configuration/framework."
        )
    return tool_path


def top_counts(items: Any, take: int = 12) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    result = []
    for item in items[:take]:
        if isinstance(item, dict):
            result.append({"Value": str(item.get("Value", "")), "Count": int(item.get("Count", 0))})
    return result


def merge_group_counts(groups: Any, field_name: str, take: int = 12) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    if isinstance(groups, list):
        for group in groups:
            if not isinstance(group, dict):
                continue
            for item in group.get(field_name, []) or []:
                if isinstance(item, dict) and item.get("Value"):
                    counter[str(item["Value"])] += int(item.get("Count", 0))
    return [{"Value": value, "Count": count} for value, count in counter.most_common(take)]


def load_schema_validator(args: argparse.Namespace) -> Callable[[Any], None] | None:
    if args.no_schema_validate:
        return None
    if not SEMANTIC_SCHEMA.exists():
        return None
    try:
        import jsonschema
    except Exception:
        return None
    schema = json.loads(SEMANTIC_SCHEMA.read_text(encoding="utf-8-sig"))
    return lambda report: jsonschema.validate(report, schema)


def run_job(
    job: DiscoveryJob, tool_path: Path, root: Path, out_dir: Path, validate_schema: Callable[[Any], None] | None
) -> DiscoveryResult:
    output_name = job.output or f"{safe_file_name(job.name)}.json"
    output_path = Path(output_name)
    if not output_path.is_absolute():
        output_path = out_dir / output_path

    cmd = [
        str(tool_path),
        job.command,
        "--root",
        str(root),
        "--out",
        str(output_path),
        "--limit",
        str(job.limit),
    ]
    if job.max_total > 0:
        cmd += ["--max-total", str(job.max_total)]
    if job.type_filter:
        cmd += ["--type", job.type_filter]
    for category in job.semantic_categories:
        if category.strip():
            cmd += ["--semantic-category", category]

    print(f"\n==> {job.name}")
    print(" ".join(cmd))
    start = time.monotonic()
    timed_out = False
    exit_code = 0
    stdout = ""
    stderr = ""
    try:
        completed = subprocess.run(cmd, text=True, capture_output=True, timeout=job.timeout_seconds)
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = -1
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""

    duration = round(time.monotonic() - start, 2)
    if stdout.strip():
        print(stdout.rstrip())
    if stderr.strip():
        print(stderr.rstrip(), file=sys.stderr)

    report: dict[str, Any] | None = None
    error_summary = None
    schema_valid: bool | None = None
    if output_path.exists():
        try:
            report = json.loads(output_path.read_text(encoding="utf-8-sig"))
            if validate_schema is not None:
                validate_schema(report)
                schema_valid = True
        except Exception as exc:  # noqa: BLE001 - summarize parse/schema failures
            schema_valid = False if report is not None else None
            error_summary = str(exc)

    if timed_out:
        error_summary = f"Timed out after {job.timeout_seconds} seconds."
    elif exit_code != 0:
        combined = (stderr + "\n" + stdout).strip()
        error_summary = (combined[:500] + "...") if len(combined) > 500 else combined
    elif output_path.exists() and report is None and error_summary is None:
        error_summary = "Output exists but could not be parsed."
    elif not output_path.exists():
        error_summary = "Output file was not created."

    entries = report.get("Entries", []) if report else []
    signature_groups = report.get("SignatureGroups", []) if report else []
    return DiscoveryResult(
        name=job.name,
        command=job.command,
        arguments=cmd[1:],
        output_path=str(output_path),
        max_total=job.max_total,
        type_filter=job.type_filter,
        semantic_categories=list(job.semantic_categories),
        timeout_seconds=job.timeout_seconds,
        duration_seconds=duration,
        exit_code=exit_code,
        timed_out=timed_out,
        parsed_report=report is not None,
        schema_version=report.get("SchemaVersion") if report else None,
        inspected_payloads=report.get("InspectedPayloads") if report else None,
        failed=report.get("Failed") if report else None,
        entry_count=len(entries) if isinstance(entries, list) else 0,
        signature_group_count=len(signature_groups) if isinstance(signature_groups, list) else 0,
        type_counts=top_counts(report.get("TypeCounts", []) if report else []),
        semantic_category_counts=top_counts(report.get("SemanticCategoryCounts", []) if report else [], take=16),
        xml_parse_status_counts=merge_group_counts(signature_groups, "XmlParseStatusCounts"),
        xml_parse_warning_counts=merge_group_counts(signature_groups, "XmlParseWarningCounts"),
        schema_valid=schema_valid,
        error_summary=error_summary,
    )


def run_privacy_scan(repo_root: Path) -> None:
    print("\n==> privacy scan")
    username_pattern = "mr" + "koo"
    user_path_pattern = r"C:\\Users\\"
    hits: list[str] = []
    for pattern in (username_pattern, user_path_pattern):
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "grep", "-n", "-I", pattern, "--", "."],
            text=True,
            capture_output=True,
        )
        if completed.returncode in (0, 1):
            hits.extend(line for line in completed.stdout.splitlines() if line.strip())
        else:
            raise RuntimeError(completed.stderr.strip() or "git grep failed")
    raw_hits = [
        hit for hit in hits if "%USERPROFILE%" not in hit and "%USERNAME%" not in hit and "<WindowsUser>" not in hit
    ]
    if raw_hits:
        print("Potential raw private path/account hits:", file=sys.stderr)
        print("\n".join(raw_hits[:20]), file=sys.stderr)
        raise RuntimeError("Privacy scan failed.")
    print("Privacy scan passed: no tracked raw username or non-placeholder C:\\Users paths.")


def print_summary_table(results: list[DiscoveryResult]) -> None:
    columns: list[tuple[str, int, Callable[[DiscoveryResult], str]]] = [
        ("Name", 30, lambda r: r.name),
        ("Exit", 4, lambda r: str(r.exit_code)),
        ("TO", 2, lambda r: "Y" if r.timed_out else "N"),
        ("Sec", 7, lambda r: f"{r.duration_seconds:.2f}"),
        ("Seen", 7, lambda r: "" if r.inspected_payloads is None else str(r.inspected_payloads)),
        ("Ent", 5, lambda r: str(r.entry_count)),
        ("Sig", 5, lambda r: str(r.signature_group_count)),
    ]
    header = " ".join(label.ljust(width) for label, width, _ in columns)
    print(header)
    print("-" * len(header))
    for result in results:
        print(" ".join(getter(result)[:width].ljust(width) for _, width, getter in columns))


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = load_matrix_jobs(args)
    tool_path = build_tool(args)
    validate_schema = load_schema_validator(args)

    started = time.time()
    results = [run_job(job, tool_path, root, out_dir, validate_schema) for job in jobs]
    failed = [r for r in results if r.timed_out or r.exit_code != 0 or not r.parsed_report or r.error_summary]
    finished = time.time()

    summary = {
        "SchemaVersion": "asset-discovery-matrix/v1",
        "GeneratedOutputNotice": "Generated from local copied RIFT assets. Keep under ignored Exports/ unless separately reviewed and redacted.",
        "RootDirectory": str(root),
        "OutputDirectory": str(out_dir),
        "MatrixPath": str(Path(args.matrix).resolve()) if args.matrix else None,
        "StartedUnix": started,
        "FinishedUnix": finished,
        "DurationSeconds": round(finished - started, 2),
        "JobCount": len(results),
        "Succeeded": len(results) - len(failed),
        "Failed": len(failed),
        "TimedOut": sum(1 for result in results if result.timed_out),
        "SchemaValidation": "skipped" if validate_schema is None else "jsonschema",
        "Jobs": [dataclasses.asdict(result) for result in results],
    }
    summary_path = out_dir / "asset-discovery-matrix-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"\n--- Discovery matrix summary: {summary_path}")
    print_summary_table(results)

    if args.privacy_scan:
        run_privacy_scan(REPO_ROOT)

    if failed and not args.allow_failures:
        print(f"Discovery matrix completed with {len(failed)} failed/timed-out/unparsed job(s).", file=sys.stderr)
        return 1
    print("Discovery matrix completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
