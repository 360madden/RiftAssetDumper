from __future__ import annotations

from scripts.build_zone_connection_graph import build_graph


def _index() -> dict:
    return {
        "generated_at": "2026-07-12T00:00:00Z",
        "zones": {
            "a.zone": {"status": "built", "bounds": {"bmin": [0, 0, 0], "bmax": [10, 10, 10]}},
            "b.zone": {"status": "built", "bounds": {"bmin": [9, 0, 5], "bmax": [20, 10, 15]}},
            "c.zone": {"status": "built", "bounds": {"bmin": [100, 0, 100], "bmax": [110, 10, 110]}},
            "failed.zone": {"status": "failed"},
        },
    }


def test_build_graph_connects_overlapping_bounds_symmetrically() -> None:
    graph = build_graph(_index())
    assert graph["summary"] == {"node_count": 3, "edge_count": 1}
    assert graph["nodes"]["a.zone"]["connected_zones"] == ["b.zone"]
    assert graph["nodes"]["b.zone"]["connected_zones"] == ["a.zone"]
    assert graph["nodes"]["c.zone"]["connected_zones"] == []
    assert graph["edges"][0]["connection_point"] == [9.5, 5.0, 7.5]


def test_build_graph_respects_gap_threshold() -> None:
    graph = build_graph(_index(), max_horizontal_gap=200)
    assert graph["summary"]["edge_count"] == 3
