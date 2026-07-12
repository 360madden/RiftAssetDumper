"""NM-6 M6.3: weighted A* routing across the M6.2 zone graph."""

from __future__ import annotations

import argparse
import heapq
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GRAPH = REPO_ROOT / "Exports" / "navmesh-phase6" / "zone-connection-graph.json"
DEFAULT_INDEX = REPO_ROOT / "Exports" / "navmesh-phase6" / "navmesh-index.json"


def _edge_map(graph: dict[str, Any]) -> dict[frozenset[str], dict[str, Any]]:
    return {frozenset((edge["a"], edge["b"])): edge for edge in graph.get("edges", [])}


def find_zone_route(graph: dict[str, Any], start_zone: str, goal_zone: str) -> list[str]:
    nodes = graph.get("nodes", {})
    if start_zone not in nodes or goal_zone not in nodes:
        raise ValueError("start and goal zones must both be built graph nodes")
    queue: list[tuple[float, str]] = [(0.0, start_zone)]
    costs = {start_zone: 0.0}
    previous: dict[str, str] = {}
    edges = _edge_map(graph)
    while queue:
        cost, current = heapq.heappop(queue)
        if current == goal_zone:
            break
        if cost > costs[current]:
            continue
        for neighbor in nodes[current].get("connected_zones", []):
            edge = edges[frozenset((current, neighbor))]
            new_cost = cost + max(float(edge.get("distance", 0.0)), 0.001)
            if new_cost < costs.get(neighbor, math.inf):
                costs[neighbor] = new_cost
                previous[neighbor] = current
                heapq.heappush(queue, (new_cost, neighbor))
    if goal_zone not in costs:
        return []
    route = [goal_zone]
    while route[-1] != start_zone:
        route.append(previous[route[-1]])
    return list(reversed(route))


def build_cross_zone_route(
    graph: dict[str, Any], start_zone: str, goal_zone: str, start: list[float], goal: list[float]
) -> dict[str, Any]:
    zones = find_zone_route(graph, start_zone, goal_zone)
    if not zones:
        return {"schema_version": "navmesh-cross-zone-route-v1", "success": False, "error": "zones disconnected"}
    edges = _edge_map(graph)
    transitions = []
    waypoints = [start]
    for a, b in zip(zones, zones[1:], strict=False):
        edge = edges[frozenset((a, b))]
        point = [float(value) for value in edge["connection_point"]]
        transitions.append({"from_zone": a, "to_zone": b, "connection_point": point})
        waypoints.append(point)
    waypoints.append(goal)
    length = sum(math.dist(a, b) for a, b in zip(waypoints, waypoints[1:], strict=False))
    return {
        "schema_version": "navmesh-cross-zone-route-v1",
        "success": True,
        "start_zone": start_zone,
        "goal_zone": goal_zone,
        "zones": zones,
        "transitions": transitions,
        "waypoints": waypoints,
        "total_length": length,
    }


def add_detour_segments(
    route: dict[str, Any], index: dict[str, Any], *, timeout: int = 180, max_transition_gap: float = 10.0
) -> dict[str, Any]:
    """Project every transition onto each zone navmesh and concatenate Detour segments."""
    if not route.get("success"):
        return route
    zones = route["zones"]
    transitions = [item["connection_point"] for item in route["transitions"]]
    endpoints = [route["waypoints"][0], *transitions, route["waypoints"][-1]]
    segments = []
    concatenated: list[list[float]] = []
    with tempfile.TemporaryDirectory(prefix="rift-cross-zone-") as temp_dir:
        for i, zone in enumerate(zones):
            entry = index.get("zones", {}).get(zone, {})
            obj_path = REPO_ROOT / entry.get("obj_path", "")
            out_path = Path(temp_dir) / f"segment-{i}.json"
            command = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "navmesh_pathfind.py"),
                "--obj",
                str(obj_path),
                "--from",
                ",".join(str(value) for value in endpoints[i]),
                "--to",
                ",".join(str(value) for value in endpoints[i + 1]),
                "--adaptive",
                "--auto-cell-size",
                "--auto-agent-params",
                "--out",
                str(out_path),
            ]
            completed = subprocess.run(
                command, cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout, check=False
            )
            if completed.returncode != 0 or not out_path.exists():
                route["detour_success"] = False
                route["error"] = f"Detour segment failed for {zone}: {completed.stderr[-500:]}"
                route["detour_segments"] = segments
                return route
            segment = json.loads(out_path.read_text(encoding="utf-8"))
            segments.append({"zone": zone, "result": segment})
            points = [item["pos"] for item in segment.get("waypoints", [])]
            if concatenated and points:
                points = points[1:]
            concatenated.extend(points)
    transition_validation = []
    for i, transition in enumerate(route["transitions"]):
        from_projection = segments[i]["result"].get("goal_pos")
        to_projection = segments[i + 1]["result"].get("start_pos")
        gap = math.dist(from_projection, to_projection) if from_projection and to_projection else math.inf
        transition_validation.append(
            {
                "from_zone": transition["from_zone"],
                "to_zone": transition["to_zone"],
                "projected_by_both_segments": from_projection is not None and to_projection is not None,
                "projection_gap": gap,
                "pass": gap <= max_transition_gap,
            }
        )
    route["detour_success"] = all(item["pass"] for item in transition_validation)
    route["detour_segments"] = segments
    route["transition_validation"] = transition_validation
    if concatenated:
        route["waypoints"] = concatenated
        route["total_length"] = sum(math.dist(a, b) for a, b in zip(concatenated, concatenated[1:], strict=False))
    return route


def _coords(value: str) -> list[float]:
    parts = [float(part) for part in value.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("coordinates must be x,y,z")
    return parts


def validate_route(route: dict[str, Any]) -> None:
    from jsonschema import Draft7Validator

    schema_path = REPO_ROOT / "docs" / "schemas" / "navmesh-cross-zone-route-v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft7Validator.check_schema(schema)
    errors = list(Draft7Validator(schema).iter_errors(route))
    if errors:
        raise ValueError("; ".join(error.message for error in errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NM-6 M6.3 cross-zone A* route")
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--detour-segments", action="store_true")
    parser.add_argument("--from-zone", required=True)
    parser.add_argument("--to-zone", required=True)
    parser.add_argument("--from", dest="start", type=_coords, required=True)
    parser.add_argument("--to", dest="goal", type=_coords, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    route = build_cross_zone_route(graph, args.from_zone, args.to_zone, args.start, args.goal)
    if args.detour_segments:
        index = json.loads(args.index.read_text(encoding="utf-8"))
        route = add_detour_segments(route, index)
    validate_route(route)
    text = json.dumps(route, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if route.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
