#!/usr/bin/env python3
"""Live family scanner — extracts new mesh-size families from live archive inventory
and generates prioritized probe/export commands.

Reads the C# mesh-binding inventory against live root (live-mesh-inventory-500.json),
identifies families not in the known copied set, and ranks them by export viability.

Usage:
    python scripts/live_family_scanner.py --inventory Exports/live-mesh-inventory-500.json
    python scripts/live_family_scanner.py --inventory Exports/live-mesh-inventory-500.json --probe
    python scripts/live_family_scanner.py --inventory Exports/live-mesh-inventory-500.json --export
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Known copied-set mesh sizes (29 families from Phase 49 project summary)
# ---------------------------------------------------------------------------
KNOWN_COPIED_MESH_SIZES: set[int] = {
    193, 197, 214, 240, 267, 272, 275, 276, 280, 297,
    301, 305, 307, 309, 321, 325, 326, 329, 330, 337,
    345, 354, 361, 365, 367, 370, 389, 405, 465,
}

# ---------------------------------------------------------------------------
# Role priority for export viability (higher = more likely exportable)
# ---------------------------------------------------------------------------
ROLE_PRIORITY: dict[str, int] = {
    "position-float3-ror1-lead": 100,
    "position-float3-lead": 95,
    "normal-float3-ror1-lead": 70,
    "normal-float3-lead": 65,
    "uv-float2-ror1-lead": 50,
    "uv-float2-lead": 45,
    "index-u16be-strip-lead": 30,
    "index-u16be-list-lead": 25,
    "index-u16be-lead": 20,
    "strided-body": 10,
    "u32-repeated-pattern-body": 5,
    "u32-sentinel-mask-body": 1,
}

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT = REPO_ROOT / "src" / "RiftAssetDumper" / "RiftAssetDumper.csproj"
DEFAULT_LIVE_ROOT = "C:/Program Files (x86)/Glyph/Games/RIFT/Live"
DEFAULT_INVENTORY = REPO_ROOT / "Exports" / "live-mesh-inventory-500.json"
DEFAULT_OUT = REPO_ROOT / "Exports"


def load_live_inventory(path: Path) -> dict[str, Any]:
    """Load live mesh-binding inventory, handling UTF-8 BOM."""
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def extract_new_families(data: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Extract mesh-size families not in the known copied set.

    Returns dict mapping mesh_size -> family info with:
        - id: asset ID prefix
        - mesh_block: mesh block index
        - archive: archive name
        - entry: entry index
        - roles: set of observed roles
        - priority: best role priority score
    """
    families: dict[int, dict[str, Any]] = {}
    role_groups = data.get("RoleGroups", [])
    if not isinstance(role_groups, list):
        return families

    for rg in role_groups:
        if not isinstance(rg, dict):
            continue
        role = rg.get("Role", "unknown")
        samples = rg.get("Samples", [])
        if not isinstance(samples, list):
            continue

        for sample in samples:
            if not isinstance(sample, dict):
                continue
            ms = sample.get("MeshSize")
            if ms is None:
                continue
            try:
                ms_int = int(ms)
            except (ValueError, TypeError):
                continue

            if ms_int in KNOWN_COPIED_MESH_SIZES:
                continue

            aid = str(sample.get("IdPrefix", ""))
            mb = sample.get("MeshBlockIndex")
            archive = str(sample.get("ArchiveName", ""))
            entry = sample.get("EntryIndex")

            if not aid or aid == "?":
                continue

            if ms_int not in families:
                families[ms_int] = {
                    "mesh_size": ms_int,
                    "id": aid,
                    "mesh_block": mb,
                    "archive": archive,
                    "entry": entry,
                    "roles": set(),
                    "priority": 0,
                }

            families[ms_int]["roles"].add(role)
            role_score = ROLE_PRIORITY.get(role, 0)
            if role_score > families[ms_int]["priority"]:
                families[ms_int]["priority"] = role_score

    return families


def rank_families(families: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank families by export viability (position > normal > UV > index > other)."""
    ranked = sorted(
        families.values(),
        key=lambda f: (f["priority"], -f["mesh_size"]),
        reverse=True,
    )
    return ranked


def _run_dotnet(args: list[str], timeout: int = 180) -> tuple[int, str, str]:
    """Run dotnet CLI directly (no Python intermediary). Returns (exit_code, stdout, stderr)."""
    cmd_str = "dotnet " + " ".join(args)
    try:
        proc = subprocess.run(
            ["dotnet", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(REPO_ROOT),
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"timeout after {timeout}s ({cmd_str[:100]}...)"
    except FileNotFoundError:
        return -1, "", "dotnet not found in PATH"
    except Exception as exc:
        return -1, "", str(exc)


def _probe_output_path(aid: str, mb: int) -> Path:
    """Return the JSON output path for a mesh probe, including mesh block to avoid overwrites."""
    return DEFAULT_OUT / f"probe-nif-mesh-{aid}-mesh{mb}.json"


def _decode_output_path(aid: str) -> Path:
    """Return the JSON output path for geometry decode."""
    return DEFAULT_OUT / f"decode-nif-geometry-{aid}.json"


def probe_family(
    family: dict[str, Any],
    live_root: str,
    skip_build: bool = False,
) -> dict[str, Any]:
    """Probe a single mesh-size family via direct dotnet CLI call.

    Calls dotnet run directly (no Python intermediary), writes output to a
    mesh-block-specific JSON path to avoid overwrites when probing multiple
    blocks of the same NIF. Parses structured JSON output for deterministic results.
    """
    aid = family["id"]
    mb = family["mesh_block"]
    out_path = _probe_output_path(aid, mb)

    result: dict[str, Any] = {
        "mesh_size": family["mesh_size"],
        "id": aid,
        "mesh_block": mb,
        "archive": family["archive"],
        "entry": family["entry"],
        "roles": sorted(family["roles"]),
        "priority": family["priority"],
        "probed": False,
        "viable": False,
        "vertex_count": 0,
        "has_position": False,
        "has_normal": False,
        "has_uv": False,
        "has_index": False,
        "pairings": 0,
        "attribute_sets": 0,
        "error": "",
    }

    # Build dotnet args directly (no Python intermediary)
    dotnet_args = [
        "run", "--project", str(DEFAULT_PROJECT), "--",
        "probe-nif-mesh",
        "--root", live_root,
        "--id", aid,
        "--mesh-block", str(mb),
        "--out", str(out_path),
    ]
    if skip_build:
        dotnet_args.insert(1, "--no-build")

    exit_code, stdout, stderr = _run_dotnet(dotnet_args, timeout=180)
    output = stdout + stderr

    # Primary: parse structured JSON output (deterministic, mesh-block-specific)
    if out_path.exists():
        try:
            with open(out_path, encoding="utf-8-sig") as f:
                probe_data = json.load(f)
            if isinstance(probe_data, dict):
                mesh_info = probe_data.get("MeshInfo", probe_data)
                if isinstance(mesh_info, dict):
                    result["vertex_count"] = int(mesh_info.get("VertexCount", 0))
                streams = probe_data.get("Streams", probe_data.get("MeshStreams", []))
                if isinstance(streams, list):
                    for stream in streams:
                        if not isinstance(stream, dict):
                            continue
                        role = str(stream.get("Role", ""))
                        if "position-float3" in role:
                            result["has_position"] = True
                        if "normal-float3" in role:
                            result["has_normal"] = True
                        if "uv-float2" in role:
                            result["has_uv"] = True
                        if "index-u16" in role:
                            result["has_index"] = True
                pairings = probe_data.get("Pairings", probe_data.get("MeshPairings", []))
                result["pairings"] = len(pairings) if isinstance(pairings, list) else 0
                attr_sets = probe_data.get("AttributeSets", probe_data.get("MeshAttributeSets", []))
                result["attribute_sets"] = len(attr_sets) if isinstance(attr_sets, list) else 0
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass  # Fall back to regex below

    # Fallback: regex parsing of stdout (kept for resilience)
    if result["vertex_count"] == 0:
        vc_match = re.search(r"VertexCount[:\s]+(\d+)", output)
        if vc_match:
            result["vertex_count"] = int(vc_match.group(1))

    if not result["has_position"] and "position-float3" in output:
        result["has_position"] = True
    if not result["has_normal"] and "normal-float3" in output:
        result["has_normal"] = True
    if not result["has_uv"] and "uv-float2" in output:
        result["has_uv"] = True
    if not result["has_index"] and ("index-u16be" in output or "index-u16le" in output):
        result["has_index"] = True

    result["probed"] = exit_code == 0
    result["viable"] = result["has_position"] and result["vertex_count"] > 0

    if exit_code != 0:
        result["error"] = output[-500:] if output else f"exit code {exit_code}"

    return result


def export_family(
    family: dict[str, Any],
    live_root: str,
    skip_build: bool = False,
) -> dict[str, Any]:
    """Export a viable mesh-size family to OBJ via direct dotnet CLI call.

    Calls dotnet run directly (no Python intermediary). Parses the structured
    JSON decode report for deterministic vertex/face counts. Locates the OBJ
    file via the known output directory convention.
    """
    aid = family["id"]
    mb = family["mesh_block"]
    decode_json_path = _decode_output_path(aid)
    obj_dir = decode_json_path  # decode-nif-geometry writes OBJ into a subdir named after the JSON

    result: dict[str, Any] = {
        "mesh_size": family["mesh_size"],
        "id": aid,
        "mesh_block": mb,
        "exported": False,
        "obj_path": "",
        "vertices": 0,
        "faces": 0,
        "file_size": 0,
        "nan_count": 0,
        "error": "",
    }

    # Build dotnet args directly (no Python intermediary)
    dotnet_args = [
        "run", "--project", str(DEFAULT_PROJECT), "--",
        "decode-nif-geometry",
        "--root", live_root,
        "--id", aid,
        "--mesh-block", str(mb),
        "--experimental-position-source",
        "--write-obj",
        "--out", str(decode_json_path),
    ]
    if skip_build:
        dotnet_args.insert(1, "--no-build")

    exit_code, stdout, stderr = _run_dotnet(dotnet_args, timeout=300)
    output = stdout + stderr

    # Primary: parse structured JSON decode report
    if decode_json_path.exists():
        try:
            with open(decode_json_path, encoding="utf-8-sig") as f:
                decode_data = json.load(f)
            if isinstance(decode_data, dict):
                result["vertices"] = int(decode_data.get("Positions", decode_data.get("VertexCount", 0)))
                result["faces"] = int(decode_data.get("Faces", 0))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass

    # Find the OBJ file in the output directory
    if isinstance(obj_dir, Path) and obj_dir.exists():
        obj_candidates = sorted(
            obj_dir.glob(f"decode-nif-geometry-mesh{mb}.obj"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if obj_candidates:
            obj_full = obj_candidates[0]
            result["obj_path"] = str(obj_full.relative_to(REPO_ROOT))
            result["file_size"] = obj_full.stat().st_size
            result["exported"] = True
            with open(obj_full, encoding="utf-8") as f:
                content = f.read()
            result["nan_count"] = content.count("nan")
            # Count vertices/faces from OBJ if JSON didn't provide them
            if result["vertices"] == 0:
                result["vertices"] = len(re.findall(r"^v ", content, re.MULTILINE))
            if result["faces"] == 0:
                result["faces"] = len(re.findall(r"^f ", content, re.MULTILINE))

    # Fallback: regex parsing of stdout
    if result["vertices"] == 0:
        v_match = re.search(r"Positions?[:\s]+(\d+)", output)
        if v_match:
            result["vertices"] = int(v_match.group(1))
    if result["faces"] == 0:
        f_match = re.search(r"Faces?[:\s]+(\d+)", output)
        if f_match:
            result["faces"] = int(f_match.group(1))

    if exit_code != 0 and not result["exported"]:
        result["error"] = output[-500:] if output else f"exit code {exit_code}"

    return result


def print_family_table(
    families: list[dict[str, Any]],
    title: str = "New Live-Only Mesh-Size Families",
) -> None:
    """Print a formatted table of families."""
    print(f"\n{'=' * 90}")
    print(f"  {title}")
    print(f"  {len(families)} families found")
    print(f"{'=' * 90}")
    print(f"  {'MS':>5}  {'AssetID':<18}  {'MB':>4}  {'Archive':<12}  {'Entry':>5}  {'Priority':>8}  {'Best Role':<35}")
    print(f"  {'-'*5}  {'-'*18}  {'-'*4}  {'-'*12}  {'-'*5}  {'-'*8}  {'-'*35}")
    for f in families:
        best_role = sorted(f["roles"], key=lambda r: ROLE_PRIORITY.get(r, 0), reverse=True)
        role_str = best_role[0] if best_role else "unknown"
        print(
            f"  {f['mesh_size']:>5}  {f['id'][:16]:<18}  {f.get('mesh_block','?'):>4}  "
            f"{f['archive']:<12}  {str(f.get('entry','?')):>5}  {f['priority']:>8}  {role_str:<35}"
        )


def print_probe_results(results: list[dict[str, Any]]) -> None:
    """Print probe results table."""
    print(f"\n{'=' * 100}")
    print("  Probe Results")
    print(f"{'=' * 100}")
    viable_count = sum(1 for r in results if r.get("viable"))
    probed_count = sum(1 for r in results if r.get("probed"))
    print(f"  Probed: {probed_count}/{len(results)}  Viable: {viable_count}/{len(results)}")
    print(f"  {'MS':>5}  {'ID':<18}  {'MB':>4}  {'Verts':>6}  {'Pos':>4}  {'Norm':>4}  {'UV':>4}  {'Pairs':>5}  {'Viable':>6}  Error")
    print(f"  {'-'*5}  {'-'*18}  {'-'*4}  {'-'*6}  {'-'*4}  {'-'*4}  {'-'*4}  {'-'*5}  {'-'*6}  {'-'*30}")
    for r in results:
        error = r.get("error", "")
        if error and len(error) > 60:
            error = error[:57] + "..."
        print(
            f"  {r['mesh_size']:>5}  {r['id'][:16]:<18}  {r['mesh_block']:>4}  "
            f"{r['vertex_count']:>6}  {str(r['has_position']):>4}  {str(r['has_normal']):>4}  "
            f"{str(r['has_uv']):>4}  {r['pairings']:>5}  {str(r['viable']):>6}  {error}"
        )


def print_export_results(results: list[dict[str, Any]]) -> None:
    """Print export results table."""
    print(f"\n{'=' * 100}")
    print("  Export Results")
    print(f"{'=' * 100}")
    exported_count = sum(1 for r in results if r.get("exported"))
    total_faces = sum(r.get("faces", 0) for r in results)
    total_verts = sum(r.get("vertices", 0) for r in results)
    print(f"  Exported: {exported_count}/{len(results)}  Faces: {total_faces}  Vertices: {total_verts}")
    print(f"  {'MS':>5}  {'Verts':>6}  {'Faces':>6}  {'Size':>8}  {'NaN':>4}  {'Status':<10}  Path")
    print(f"  {'-'*5}  {'-'*6}  {'-'*6}  {'-'*8}  {'-'*4}  {'-'*10}  {'-'*40}")
    for r in results:
        status = "OK" if r.get("exported") else "FAIL"
        print(
            f"  {r['mesh_size']:>5}  {r['vertices']:>6}  {r['faces']:>6}  "
            f"{r['file_size']:>8}  {r['nan_count']:>4}  {status:<10}  {r.get('obj_path', r.get('error',''))[:40]}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Live family scanner — extract new mesh-size families from live inventory"
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=DEFAULT_INVENTORY,
        help=f"Path to live mesh-binding inventory JSON (default: {DEFAULT_INVENTORY})",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Probe each new family to assess export viability",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export viable families to OBJ (implies --probe)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit to top N families by priority (0 = all)",
    )
    parser.add_argument(
        "--json",
        type=Path,
        help="Write structured results to JSON file",
    )
    parser.add_argument(
        "--live-root",
        type=str,
        default=DEFAULT_LIVE_ROOT,
        help=f"Path to live RIFT install (default: {DEFAULT_LIVE_ROOT})",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        default=False,
        help="Skip dotnet build before each probe/export (use after initial build for faster repeated runs)",
    )
    args = parser.parse_args()

    if not args.inventory.exists():
        print(f"ERROR: Inventory file not found: {args.inventory}", file=sys.stderr)
        print(
            "  Run: dotnet run --project src/RiftAssetDumper -- inventory-nif-mesh-bindings"
            f' --root "{DEFAULT_LIVE_ROOT}" --max-total 500 --out Exports/live-mesh-inventory-500.json',
            file=sys.stderr,
        )
        sys.exit(1)

    # Step 1: Extract
    data = load_live_inventory(args.inventory)
    families = extract_new_families(data)
    ranked = rank_families(families)

    if args.limit > 0:
        ranked = ranked[: args.limit]

    print_family_table(ranked)

    # Step 2: Probe (if requested)
    probe_results: list[dict[str, Any]] = []
    if args.probe or args.export:
        print("\nProbing families...")
        for i, family in enumerate(ranked):
            print(f"  [{i+1}/{len(ranked)}] MeshSize={family['mesh_size']} id={family['id'][:16]} mb={family['mesh_block']} ...")
            result = probe_family(family, live_root=args.live_root, skip_build=args.skip_build)
            probe_results.append(result)
            status = "VIABLE" if result["viable"] else ("probed" if result["probed"] else "FAILED")
            print(f"    -> {status} v={result['vertex_count']} pos={result['has_position']} norm={result['has_normal']} uv={result['has_uv']}")

        print_probe_results(probe_results)

    # Step 3: Export (if requested)
    export_results: list[dict[str, Any]] = []
    if args.export:
        viable = [r for r in probe_results if r["viable"]]
        if not viable:
            print("\nNo viable families to export.")
        else:
            print(f"\nExporting {len(viable)} viable families...")
            for i, pr in enumerate(viable):
                family_info = {
                    "mesh_size": pr["mesh_size"],
                    "id": pr["id"],
                    "mesh_block": pr["mesh_block"],
                }
                print(f"  [{i+1}/{len(viable)}] MeshSize={pr['mesh_size']} ...")
                result = export_family(family_info, live_root=args.live_root, skip_build=args.skip_build)
                export_results.append(result)
                status = "OK" if result["exported"] else "FAIL"
                print(f"    -> {status} v={result['vertices']} f={result['faces']} size={result['file_size']}")

            print_export_results(export_results)

    # Write JSON output
    if args.json:
        output = {
            "schema": "live-family-scanner/v1",
            "inventory": str(args.inventory),
            "known_copied_families": len(KNOWN_COPIED_MESH_SIZES),
            "new_families_found": len(ranked),
            "families": [
                {
                    "mesh_size": f["mesh_size"],
                    "id": f["id"],
                    "mesh_block": f["mesh_block"],
                    "archive": f["archive"],
                    "entry": f["entry"],
                    "roles": sorted(f["roles"]),
                    "priority": f["priority"],
                }
                for f in ranked
            ],
            "probe_results": probe_results if probe_results else None,
            "export_results": export_results if export_results else None,
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(output, indent=2), encoding="utf-8")
        print(f"\nResults written to: {args.json}")

    # Summary
    print(f"\nSummary: {len(ranked)} new families extracted from {args.inventory.name}")
    if probe_results:
        viable = sum(1 for r in probe_results if r["viable"])
        print(f"  Probed: {sum(1 for r in probe_results if r['probed'])}/{len(probe_results)}")
        print(f"  Viable: {viable}/{len(probe_results)}")
    if export_results:
        exported = sum(1 for r in export_results if r["exported"])
        total_f = sum(r.get("faces", 0) for r in export_results)
        total_v = sum(r.get("vertices", 0) for r in export_results)
        print(f"  Exported: {exported}/{len(export_results)}")
        print(f"  Total faces: {total_f}, Total vertices: {total_v}")


if __name__ == "__main__":
    main()
