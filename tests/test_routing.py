import networkx as nx
import numpy as np
import pytest

from ayus.config import PlannerConfig
from ayus.image_processing import GridSpec
from ayus.metrics import path_length_pixels
from ayus.routing import build_graph, choose_endpoints, generate_backup_routes, path_overlap_ratio


def _grid(height=20, width=30, rows=4, cols=5):
    return GridSpec(
        height,
        width,
        rows,
        cols,
        np.linspace(0, height, rows + 1, dtype=np.int32),
        np.linspace(0, width, cols + 1, dtype=np.int32),
    )


def test_grid_metric_uses_real_pixel_geometry():
    grid = _grid()
    assert path_length_pixels([(0, 0), (0, 1)], grid) == 6.0
    assert path_length_pixels([(0, 0), (1, 0)], grid) == 5.0


def test_graph_does_not_allow_diagonal_corner_cutting():
    grid = _grid()
    blocked = np.zeros((4, 5), dtype=bool)
    blocked[0, 1] = True
    blocked[1, 0] = True
    graph = build_graph(
        blocked, np.zeros((4, 5), dtype=np.float32), np.ones((4, 5), dtype=np.float32), grid, PlannerConfig()
    )
    assert not graph.has_edge((0, 0), (1, 1))


def test_backup_routes_are_not_duplicate_paths():
    graph = nx.grid_2d_graph(4, 4)
    for u, v in graph.edges:
        graph.edges[u, v]["weight"] = 1.0
    config = PlannerConfig(alternative_route_count=3)
    primary = nx.shortest_path(graph, (0, 0), (3, 3))
    routes = generate_backup_routes(graph, (0, 0), (3, 3), primary, config)
    assert len({tuple(route) for route in routes}) == len(routes)
    assert all(path_overlap_ratio(route, primary) <= 1.0 for route in routes)


@pytest.mark.parametrize("fragmented", [False, True])
def test_large_grid_endpoint_selection_reuses_distance_searches(monkeypatch, fragmented):
    side = 80
    graph = nx.grid_2d_graph(side, side)
    if fragmented:
        graph.remove_nodes_from((row, side // 2) for row in range(side))
        start_target, end_target = (5, side // 2), (74, side // 2)
    else:
        start_target, end_target = (0, 0), (side - 1, side - 1)
        graph.remove_nodes_from((start_target, end_target))
    nx.set_node_attributes(graph, 1.0, "clearance")
    nx.set_edge_attributes(graph, 1.0, "weight")
    risk = np.zeros((side, side), dtype=np.float32)
    clearance = np.ones((side, side), dtype=np.float32)

    searches = 0
    original_search = nx.single_source_dijkstra_path_length

    def count_searches(*args, **kwargs):
        nonlocal searches
        searches += 1
        return original_search(*args, **kwargs)

    monkeypatch.setattr(nx, "single_source_dijkstra_path_length", count_searches)
    start, end = choose_endpoints(graph, risk, clearance, start_target, end_target)

    assert start in graph and end in graph
    assert nx.has_path(graph, start, end)
    assert 1 <= searches <= 25
