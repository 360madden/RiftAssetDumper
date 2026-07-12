from scripts.export_navigation_debug_obj import export_debug_obj


def test_export_graph_and_route(tmp_path) -> None:
    graph = {
        "nodes": {
            "a": {"bounds": {"bmin": [0, 0, 0], "bmax": [2, 2, 2]}},
            "b": {"bounds": {"bmin": [2, 0, 0], "bmax": [4, 2, 2]}},
        },
        "edges": [{"a": "a", "b": "b"}],
    }
    out = tmp_path / "debug.obj"
    export_debug_obj(graph, {"waypoints": [[0, 0, 0], [4, 0, 0]]}, out)
    text = out.read_text()
    assert text.count("\nv ") == 4
    assert text.count("\nl ") == 2
