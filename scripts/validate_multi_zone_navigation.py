"""NM-6 M6.4: validate graph symmetry, route continuity, and route latency."""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.cross_zone_pathfind import build_cross_zone_route  # noqa: E402

DEFAULT_GRAPH = REPO_ROOT / "Exports" / "navmesh-phase6" / "zone-connection-graph.json"
DEFAULT_OUT = REPO_ROOT / "Exports" / "navmesh-phase6" / "multi-zone-validation.json"


def validate_multi_zone(graph: dict[str, Any], *, max_route_ms: float = 100.0) -> dict[str, Any]:
    failures: list[str] = []
    disconnected_pairs: list[str] = []
    nodes = graph.get("nodes", {})
    for name, node in nodes.items():
        for neighbor in node.get("connected_zones", []):
            if neighbor not in nodes or name not in nodes.get(neighbor, {}).get("connected_zones", []):
                failures.append(f"asymmetric edge {name}->{neighbor}")
    timings: list[float] = []
    route_count = 0
    max_zone_count = 0
    for start_zone, goal_zone in itertools.combinations(sorted(nodes), 2):
        start = nodes[start_zone]["bounds"]["bmin"]
        goal = nodes[goal_zone]["bounds"]["bmax"]
        before = time.perf_counter()
        route = build_cross_zone_route(graph, start_zone, goal_zone, start, goal)
        elapsed_ms = (time.perf_counter() - before) * 1000.0
        timings.append(elapsed_ms)
        if not route.get("success"):
            disconnected_pairs.append(f"{start_zone}->{goal_zone}")
            continue
        route_count += 1
        max_zone_count = max(max_zone_count, len(route["zones"]))
        if len(route["transitions"]) != len(route["zones"]) - 1:
            failures.append(f"transition discontinuity {start_zone}->{goal_zone}")
    max_ms = max(timings, default=0.0)
    if max_ms > max_route_ms:
        failures.append(f"route latency {max_ms:.3f}ms exceeds {max_route_ms:.3f}ms")
    return {
        "schema_version": "navmesh-multi-zone-validation-v1",
        "success": not failures,
        "summary": {
            "node_count": len(nodes),
            "route_count": route_count,
            "max_zone_count": max_zone_count,
            "max_route_ms": max_ms,
            "disconnected_pair_count": len(disconnected_pairs),
        },
        "failures": failures,
        "disconnected_pairs": disconnected_pairs,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate NM-6 multi-zone routing")
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-route-ms", type=float, default=100.0)
    args = parser.parse_args(argv)
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    report = validate_multi_zone(graph, max_route_ms=args.max_route_ms)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
