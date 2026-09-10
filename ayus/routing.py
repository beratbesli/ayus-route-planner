from __future__ import annotations

import math
from collections.abc import Callable

import networkx as nx
import numpy as np

from .config import PlannerConfig
from .image_processing import GridSpec

Node = tuple[int, int]


def edge_key(u: Node, v: Node) -> tuple[Node, Node]:
    return tuple(sorted((u, v)))


def path_cost(graph: nx.Graph, path: list[Node]) -> float:
    return sum(float(graph.edges[path[index], path[index + 1]]["weight"]) for index in range(len(path) - 1))


def _add_weighted_edge(graph, u, v, grid, risk_map, clearance_map, config) -> None:
    avg_risk = float((risk_map[u] + risk_map[v]) * 0.5)
    avg_clearance = float((clearance_map[u] + clearance_map[v]) * 0.5)
    ux, uy = grid.center(u)
    vx, vy = grid.center(v)
    physical_step = math.hypot(vx - ux, vy - uy)
    weight = physical_step * (
        1.0 + avg_risk * config.risk_edge_weight + (1.0 - avg_clearance) * config.clearance_edge_weight
    )
    graph.add_edge(u, v, weight=float(weight))


def build_graph(blocked_mask, risk_map, clearance_map, grid: GridSpec, config: PlannerConfig) -> nx.Graph:
    graph = nx.Graph()
    rows, cols = blocked_mask.shape
    for row in range(rows):
        for col in range(cols):
            if not blocked_mask[row, col]:
                graph.add_node((row, col), risk=float(risk_map[row, col]), clearance=float(clearance_map[row, col]))

    orthogonal = ((1, 0), (-1, 0), (0, 1), (0, -1))
    diagonal = ((1, 1), (1, -1), (-1, 1), (-1, -1))
    for row, col in list(graph.nodes):
        current = (row, col)
        for delta_row, delta_col in orthogonal:
            neighbor = (row + delta_row, col + delta_col)
            if neighbor in graph and not graph.has_edge(current, neighbor):
                _add_weighted_edge(graph, current, neighbor, grid, risk_map, clearance_map, config)
        for delta_row, delta_col in diagonal:
            neighbor = (row + delta_row, col + delta_col)
            side_a = (row + delta_row, col)
            side_b = (row, col + delta_col)
            if neighbor in graph and side_a in graph and side_b in graph and not graph.has_edge(current, neighbor):
                _add_weighted_edge(graph, current, neighbor, grid, risk_map, clearance_map, config)
    return graph


def find_corner_anchor(blocked_mask, risk_map, clearance_map, corner: str) -> Node | None:
    rows, cols = blocked_mask.shape
    depth = max(2, min(rows, cols) // 8)
    corner_span = max(4, min(rows, cols) // 3)
    candidates = []
    for row in range(rows):
        for col in range(cols):
            if blocked_mask[row, col]:
                continue
            if corner == "top_left":
                near_border = row < depth or col < depth
                corner_distance = row + col
            elif corner == "bottom_right":
                near_border = row >= rows - depth or col >= cols - depth
                corner_distance = (rows - 1 - row) + (cols - 1 - col)
            else:
                raise ValueError(f"Desteklenmeyen köşe: {corner}")
            if not near_border or corner_distance > corner_span:
                continue
            score = (
                corner_distance
                + risk_map[row, col] * min(rows, cols) * 3.0
                - clearance_map[row, col] * min(rows, cols) * 2.0
            )
            candidates.append((float(score), (row, col)))
    return min(candidates, default=(0.0, None), key=lambda item: item[0])[1]


def _rank_candidates(graph, target: Node, risk_map, clearance_map, limit: int = 25):
    rows, cols = risk_map.shape
    distance_limit = max(6, min(rows, cols) // 3)
    candidates = []
    for node in graph.nodes:
        distance = abs(node[0] - target[0]) + abs(node[1] - target[1])
        if distance <= distance_limit:
            score = distance + risk_map[node] * min(rows, cols) * 4.0 - clearance_map[node] * min(rows, cols) * 2.5
            candidates.append((float(score), node))
    if not candidates:
        for node in graph.nodes:
            distance = abs(node[0] - target[0]) + abs(node[1] - target[1])
            score = distance + risk_map[node] * min(rows, cols) * 4.0 - clearance_map[node] * min(rows, cols) * 2.5
            candidates.append((float(score), node))
    return sorted(candidates)[:limit]


def choose_endpoints(
    graph, risk_map, clearance_map, start_target: Node, end_target: Node
) -> tuple[Node | None, Node | None]:
    if not graph:
        return None, None
    node_to_component = {}
    for component_index, component in enumerate(nx.connected_components(graph)):
        for node in component:
            node_to_component[node] = component_index
    # The planner's anchors (and explicit user targets) are already selected
    # from safe cells. Preserve them when they share a connected component;
    # moving an endpoint toward the interior can otherwise make a clear image
    # start at (0, 2), for example, simply because that shortens the graph
    # path by a few pixels.
    if (
        start_target in graph
        and end_target in graph
        and node_to_component[start_target] == node_to_component[end_target]
    ):
        return start_target, end_target
    starts = _rank_candidates(graph, start_target, risk_map, clearance_map)
    ends = _rank_candidates(graph, end_target, risk_map, clearance_map)
    best = (float("inf"), None, None)
    for start_score, start in starts:
        for end_score, end in ends:
            if start == end or node_to_component[start] != node_to_component[end]:
                continue
            try:
                corridor_cost = nx.shortest_path_length(graph, start, end, weight="weight")
            except nx.NetworkXNoPath:
                continue
            endpoint_clearance = graph.nodes[start]["clearance"] + graph.nodes[end]["clearance"]
            score = corridor_cost + (start_score + end_score) * 3.5 - endpoint_clearance * 8.0
            if score < best[0]:
                best = (float(score), start, end)
    return best[1], best[2]


def run_aco(graph: nx.Graph, start: Node, end: Node, config: PlannerConfig) -> tuple[list[Node], float]:
    pheromone = {edge_key(u, v): 1.0 for u, v in graph.edges}
    best_path: list[Node] = []
    best_cost = float("inf")
    rng = np.random.default_rng(config.seed)
    max_steps = max(10, len(graph.nodes))
    distance_to_end = nx.single_source_dijkstra_path_length(graph, end, weight="weight")
    for _ in range(config.aco_iterations):
        successful_paths = []
        for _ in range(config.aco_ants):
            current = start
            path = [current]
            visited = {current}
            while current != end and len(path) < max_steps:
                choices, weights = [], []
                for neighbor in sorted(graph.neighbors(current)):
                    if neighbor in visited:
                        continue
                    pheromone_value = pheromone[edge_key(current, neighbor)] ** config.aco_alpha
                    cost_term = 1.0 / max(float(graph.edges[current, neighbor]["weight"]), 1e-9)
                    goal_distance = distance_to_end.get(neighbor, float("inf"))
                    goal_term = 0.0 if not math.isfinite(goal_distance) else 1.0 / (1.0 + goal_distance)
                    choices.append(neighbor)
                    weights.append(pheromone_value * cost_term**config.aco_beta * goal_term**config.aco_gamma)
                if not choices:
                    break
                weight_array = np.asarray(weights, dtype=np.float64)
                weight_sum = float(weight_array.sum())
                probabilities = (
                    np.full(len(choices), 1.0 / len(choices))
                    if not np.isfinite(weight_sum) or weight_sum <= 0
                    else weight_array / weight_sum
                )
                current = choices[int(rng.choice(len(choices), p=probabilities))]
                path.append(current)
                visited.add(current)
            if current == end:
                cost = path_cost(graph, path)
                successful_paths.append((path, cost))
                if cost < best_cost:
                    best_path, best_cost = path, cost
        for edge, value in pheromone.items():
            pheromone[edge] = max(0.05, value * (1.0 - config.aco_evaporation))
        for path, cost in successful_paths:
            deposit = config.aco_deposit / max(cost, 1e-6)
            for index in range(len(path) - 1):
                pheromone[edge_key(path[index], path[index + 1])] += deposit
    return best_path, best_cost


def path_overlap_ratio(path_a: list[Node], path_b: list[Node]) -> float:
    set_a = set(path_a[1:-1] if len(path_a) > 2 else path_a)
    set_b = set(path_b[1:-1] if len(path_b) > 2 else path_b)
    if not set_a or not set_b:
        return 1.0
    return len(set_a & set_b) / max(1, min(len(set_a), len(set_b)))


def generate_backup_routes(
    graph: nx.Graph, start: Node, end: Node, primary_path: list[Node], config: PlannerConfig
) -> list[list[Node]]:
    if not primary_path:
        return []
    routes = [primary_path]
    penalties = {}

    def penalize(path, amount):
        for index in range(len(path) - 1):
            edge = edge_key(path[index], path[index + 1])
            penalties[edge] = penalties.get(edge, 0.0) + amount

    penalize(primary_path, 2.5)
    for attempt in range(1, config.alternative_search_attempts + 1):
        if len(routes) >= config.alternative_route_count:
            break
        weight: Callable = lambda u, v, data: float(data["weight"]) + penalties.get(edge_key(u, v), 0.0)
        try:
            candidate = nx.shortest_path(graph, start, end, weight=weight)
        except nx.NetworkXNoPath:
            break
        if candidate in routes:
            penalize(candidate, 1.0 + attempt * 0.25)
            continue
        overlap = max(path_overlap_ratio(candidate, route) for route in routes)
        if overlap < config.alternative_overlap_limit:
            routes.append(candidate)
            penalize(candidate, 2.5 + len(routes))
        else:
            penalize(candidate, 1.0 + attempt * 0.25)
    return routes
