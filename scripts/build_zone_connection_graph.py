"""NM-6 M6.2: build a deterministic zone adjacency graph from navmesh bounds."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = REPO_ROOT / "Exports" / "navmesh-phase6" / "navmesh-index.json"
DEFAULT_OUT = REPO_ROOT / "Exports" / "navmesh-phase6" / "zone-connection-graph.json"
SCHEMA_PATH = REPO_ROOT / "docs" / "schemas" / "zone-connection-graph-v1.schema.json"
SCHEMA_VERSION = "zone-connection-graph-v1"


def _axis_gap(a_min: float, a_max: float, b_min: float, b_max: float) -> float:
    return max(0.0, b_min - a_max, a_min - b_max)


def _connection_point(a: dict[str, list[float]], b: dict[str, list[float]]) -> list[float]:
    point: list[float] = []
    for axis in range(3):
        lo = max(float(a["bmin"][axis]), float(b["bmin"][axis]))
        hi = min(float(a["bmax"][axis]), float(b["bmax"][axis]))
        if lo <= hi:
            point.append((lo + hi) / 2.0)
        else:
            left = min(float(a["bmax"][axis]), float(b["bmax"][axis]))
            right = max(float(a["bmin"][axis]), float(b["bmin"][axis]))
            point.append((left + right) / 2.0)
    return point


def _debug_vertices(entry: dict[str, Any]) -> list[tuple[float, float, float]]:
    relative = entry.get("debug_navmesh_path")
    if not relative:
        return []
    path = REPO_ROOT / relative
    if not path.exists():
        return []
    return [tuple(map(float, line.split()[1:4])) for line in path.read_text().splitlines() if line.startswith("v ")]


def build_graph(
    index: dict[str, Any], *, max_horizontal_gap: float = 10.0, max_vertical_gap: float = 10.0
) -> dict[str, Any]:
    built = {
        name: entry
        for name, entry in index.get("zones", {}).items()
        if entry.get("status") == "built" and isinstance(entry.get("bounds"), dict)
    }
    adjacency = {name: [] for name in sorted(built)}
    edges: list[dict[str, Any]] = []
    names = sorted(built)
    for i, a_name in enumerate(names):
        for b_name in names[i + 1 :]:
            a = built[a_name]["bounds"]
            b = built[b_name]["bounds"]
            a_vertices = _debug_vertices(built[a_name])
            b_vertices = _debug_vertices(built[b_name])
            if a_vertices and b_vertices:
                distance, pair = min(
                    (math.dist(left, right), (left, right)) for left in a_vertices for right in b_vertices
                )
                if distance > max_horizontal_gap:
                    continue
                connection_point = [(pair[0][axis] + pair[1][axis]) / 2.0 for axis in range(3)]
                method = "navmesh-vertex-proximity"
            else:
                connection_point = _connection_point(a, b)
                method = "bounds-proximity"
            gx = _axis_gap(a["bmin"][0], a["bmax"][0], b["bmin"][0], b["bmax"][0])
            gy = _axis_gap(a["bmin"][1], a["bmax"][1], b["bmin"][1], b["bmax"][1])
            gz = _axis_gap(a["bmin"][2], a["bmax"][2], b["bmin"][2], b["bmax"][2])
            horizontal = math.hypot(gx, gz)
            if not a_vertices and (horizontal > max_horizontal_gap or gy > max_vertical_gap):
                continue
            adjacency[a_name].append(b_name)
            adjacency[b_name].append(a_name)
            edges.append(
                {
                    "a": a_name,
                    "b": b_name,
                    "distance": distance if a_vertices else math.hypot(horizontal, gy),
                    "connection_point": connection_point,
                    "method": method,
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_index_generated_at": index.get("generated_at", ""),
        "parameters": {"max_horizontal_gap": max_horizontal_gap, "max_vertical_gap": max_vertical_gap},
        "nodes": {
            name: {"bounds": built[name]["bounds"], "connected_zones": sorted(adjacency[name])} for name in names
        },
        "edges": sorted(edges, key=lambda edge: (edge["a"], edge["b"])),
        "summary": {"node_count": len(names), "edge_count": len(edges)},
    }


def validate_graph(graph: dict[str, Any]) -> None:
    from jsonschema import Draft7Validator, FormatChecker

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft7Validator.check_schema(schema)
    errors = list(Draft7Validator(schema, format_checker=FormatChecker()).iter_errors(graph))
    if errors:
        raise ValueError("; ".join(error.message for error in errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build NM-6 M6.2 zone adjacency graph")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-horizontal-gap", type=float, default=10.0)
    parser.add_argument("--max-vertical-gap", type=float, default=10.0)
    parser.add_argument("--no-update-index", action="store_true")
    args = parser.parse_args(argv)
    index = json.loads(args.index.read_text(encoding="utf-8"))
    if index.get("run", {}).get("scope") != "full":
        print("ERROR: M6.2 requires a full-scope navmesh index", file=__import__("sys").stderr)
        return 2
    graph = build_graph(index, max_horizontal_gap=args.max_horizontal_gap, max_vertical_gap=args.max_vertical_gap)
    validate_graph(graph)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    if not args.no_update_index:
        for name, node in graph["nodes"].items():
            index["zones"][name]["connected_zones"] = node["connected_zones"]
        args.index.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(f"M6.2 graph: nodes={graph['summary']['node_count']} edges={graph['summary']['edge_count']} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
