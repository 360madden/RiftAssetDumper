from __future__ import annotations

from scripts.cross_zone_pathfind import build_cross_zone_route, find_zone_route


def _graph() -> dict:
    return {
        "nodes": {
            "a.zone": {"connected_zones": ["b.zone"]},
            "b.zone": {"connected_zones": ["a.zone", "c.zone"]},
            "c.zone": {"connected_zones": ["b.zone"]},
            "d.zone": {"connected_zones": []},
        },
        "edges": [
            {"a": "a.zone", "b": "b.zone", "distance": 1, "connection_point": [1, 0, 0]},
            {"a": "b.zone", "b": "c.zone", "distance": 1, "connection_point": [2, 0, 0]},
        ],
    }


def test_find_zone_route_uses_a_star_costs() -> None:
    assert find_zone_route(_graph(), "a.zone", "c.zone") == ["a.zone", "b.zone", "c.zone"]


def test_disconnected_route_is_reported() -> None:
    assert find_zone_route(_graph(), "a.zone", "d.zone") == []


def test_cross_zone_route_concatenates_transitions() -> None:
    route = build_cross_zone_route(_graph(), "a.zone", "c.zone", [0, 0, 0], [3, 0, 0])
    assert route["success"] is True
    assert route["waypoints"] == [[0, 0, 0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [3, 0, 0]]
    assert route["total_length"] == 3.0
