from __future__ import annotations

from scripts.validate_multi_zone_navigation import validate_multi_zone


def test_multi_zone_validation_passes_connected_graph() -> None:
    graph = {
        "nodes": {
            "a.zone": {"connected_zones": ["b.zone"], "bounds": {"bmin": [0, 0, 0], "bmax": [1, 1, 1]}},
            "b.zone": {"connected_zones": ["a.zone"], "bounds": {"bmin": [1, 0, 0], "bmax": [2, 1, 1]}},
        },
        "edges": [{"a": "a.zone", "b": "b.zone", "distance": 0, "connection_point": [1, 0, 0]}],
    }
    report = validate_multi_zone(graph)
    assert report["success"] is True
    assert report["summary"]["route_count"] == 1


def test_multi_zone_validation_rejects_asymmetry() -> None:
    graph = {
        "nodes": {
            "a.zone": {"connected_zones": ["b.zone"], "bounds": {"bmin": [0, 0, 0], "bmax": [1, 1, 1]}},
            "b.zone": {"connected_zones": [], "bounds": {"bmin": [1, 0, 0], "bmax": [2, 1, 1]}},
        },
        "edges": [{"a": "a.zone", "b": "b.zone", "distance": 0, "connection_point": [1, 0, 0]}],
    }
    assert validate_multi_zone(graph)["success"] is False


def test_multi_zone_validation_covers_five_plus_zone_route() -> None:
    names = [f"z{i}.zone" for i in range(6)]
    nodes = {}
    edges = []
    for i, name in enumerate(names):
        neighbors = []
        if i:
            neighbors.append(names[i - 1])
        if i + 1 < len(names):
            neighbors.append(names[i + 1])
            edges.append({"a": name, "b": names[i + 1], "distance": 1, "connection_point": [float(i + 1), 0, 0]})
        nodes[name] = {
            "connected_zones": neighbors,
            "bounds": {"bmin": [i, 0, 0], "bmax": [i + 1, 1, 1]},
        }
    report = validate_multi_zone({"nodes": nodes, "edges": edges})
    assert report["success"] is True
    assert report["summary"]["route_count"] == 15
    assert report["summary"]["max_zone_count"] == 6
