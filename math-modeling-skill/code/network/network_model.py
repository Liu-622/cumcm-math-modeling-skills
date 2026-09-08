"""Shortest-route skeleton with an explicit network semantics contract.

Define what nodes, edges and weights mean before building the graph.  Do not
use shortest path when capacities, simultaneous vehicles or scheduling couple
the decisions; those require flow, VRP or scheduling formulations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable, Iterable

import networkx as nx
import numpy as np


Node = Hashable
Edge = tuple[Node, Node, float]


@dataclass(frozen=True)
class NetworkSchema:
    node_meaning: str
    edge_meaning: str
    weight_meaning: str
    directed: bool


@dataclass(frozen=True)
class PathResult:
    nodes: tuple[Node, ...]
    total_weight: float


@dataclass(frozen=True)
class PathSensitivity:
    base: PathResult
    path_change_rate: float
    perturbed_weight_interval: tuple[float, float]


def build_graph(schema: NetworkSchema, edges: Iterable[Edge]) -> nx.Graph:
    """Build a weighted graph after validating the Dijkstra weight assumptions."""
    if not schema.node_meaning or not schema.edge_meaning or not schema.weight_meaning:
        raise ValueError("network semantics must be documented")
    graph: nx.Graph = nx.DiGraph() if schema.directed else nx.Graph()
    count = 0
    for source, target, weight in edges:
        value = float(weight)
        if not np.isfinite(value) or value < 0:
            raise ValueError("shortest-path edge weights must be finite and non-negative")
        graph.add_edge(source, target, weight=value)
        count += 1
    if count == 0:
        raise ValueError("at least one edge is required")
    return graph


def shortest_route(graph: nx.Graph, source: Node, target: Node) -> PathResult:
    """Return both the route and its declared weight; fail clearly if disconnected."""
    if source not in graph or target not in graph:
        raise KeyError("source and target must exist in the graph")
    try:
        nodes = nx.shortest_path(graph, source, target, weight="weight", method="dijkstra")
        total = nx.path_weight(graph, nodes, weight="weight")
    except nx.NetworkXNoPath as exc:
        raise ValueError(f"no route exists from {source!r} to {target!r}") from exc
    return PathResult(tuple(nodes), float(total))


def perturbation_test(
    graph: nx.Graph,
    source: Node,
    target: Node,
    *,
    relative_noise: float = 0.05,
    replications: int = 200,
    seed: int = 0,
) -> PathSensitivity:
    """Measure route instability under independent bounded weight perturbations."""
    if not 0 < relative_noise < 1 or replications < 2:
        raise ValueError("relative_noise must be in (0, 1) and replications at least 2")
    base = shortest_route(graph, source, target)
    rng = np.random.default_rng(seed)
    changed, weights = 0, []
    for _ in range(replications):
        perturbed = graph.copy()
        for u, v, attributes in perturbed.edges(data=True):
            attributes["weight"] *= rng.uniform(1 - relative_noise, 1 + relative_noise)
        route = shortest_route(perturbed, source, target)
        changed += route.nodes != base.nodes
        weights.append(route.total_weight)
    interval = tuple(float(v) for v in np.quantile(weights, [0.025, 0.975]))
    return PathSensitivity(base, changed / replications, interval)


def _smoke_test() -> None:
    graph = build_graph(
        NetworkSchema("locations", "available roads", "travel time", directed=False),
        [("A", "B", 2.0), ("B", "C", 2.0), ("A", "C", 5.0)],
    )
    route = shortest_route(graph, "A", "C")
    sensitivity = perturbation_test(graph, "A", "C", replications=20)
    assert route.nodes == ("A", "B", "C") and sensitivity.base.total_weight == 4.0


if __name__ == "__main__":
    _smoke_test()
    print("network skeleton: OK")
