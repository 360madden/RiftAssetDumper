"""Export M6.2 graph edges and an optional M6.3 route as a line-based OBJ."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def export_debug_obj(graph: dict[str, Any], route: dict[str, Any] | None, out: Path) -> None:
    lines = ["# NM-6 graph/path debug OBJ"]
    vertex_count = 0
    for edge in graph.get("edges", []):
        a = graph["nodes"][edge["a"]]["bounds"]
        b = graph["nodes"][edge["b"]]["bounds"]
        for bounds in (a, b):
            point = [(bounds["bmin"][i] + bounds["bmax"][i]) / 2 for i in range(3)]
            lines.append(f"v {point[0]} {point[1]} {point[2]}")
        lines.append(f"l {vertex_count + 1} {vertex_count + 2}")
        vertex_count += 2
    if route:
        indices = []
        for point in route.get("waypoints", []):
            lines.append(f"v {point[0]} {point[1]} {point[2]}")
            vertex_count += 1
            indices.append(str(vertex_count))
        if len(indices) >= 2:
            lines.append("l " + " ".join(indices))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--route", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    route = json.loads(args.route.read_text(encoding="utf-8")) if args.route else None
    export_debug_obj(graph, route, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
