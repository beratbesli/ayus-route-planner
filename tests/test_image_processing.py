import numpy as np

from ayus.config import PlannerConfig
from ayus.image_processing import build_grid, build_risk_maps
from ayus.planner import generate_route_plan


def test_grid_covers_every_pixel_for_uneven_dimensions():
    image = np.zeros((13, 17, 3), dtype=np.uint8)
    config = PlannerConfig(grid_rows=4, grid_cols=5)

    grid = build_grid(image, config)

    assert grid.bounds((0, 0))[:2] == (0, 3)
    assert grid.bounds((3, 4)) == (9, 13, 13, 17)
    assert int(np.diff(grid.row_edges).sum()) == image.shape[0]
    assert int(np.diff(grid.col_edges).sum()) == image.shape[1]


def test_blank_image_has_no_blocked_cells():
    image = np.zeros((20, 20, 3), dtype=np.uint8)
    maps = build_risk_maps(image, PlannerConfig(grid_rows=5, grid_cols=5))

    assert not maps.blocked_mask.any()
    assert np.all(maps.raw_risk == 0)


def test_planner_produces_a_deterministic_route_on_clear_image():
    image = np.zeros((30, 30, 3), dtype=np.uint8)
    config = PlannerConfig(grid_rows=6, grid_cols=6, alternative_route_count=2)

    plan = generate_route_plan(image, config)

    assert plan.start_node == (0, 0)
    assert plan.end_node == (5, 5)
    assert len(plan.routes) == 2
    assert plan.routes[0][0] == plan.start_node
    assert plan.routes[0][-1] == plan.end_node
