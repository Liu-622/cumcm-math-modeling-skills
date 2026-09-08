"""Reproducible Monte Carlo skeleton with paired scenario comparison.

The simulator must encode a justified mechanism or policy.  Random sampling
cannot compensate for unsupported transition rules or input distributions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

import numpy as np
from numpy.typing import NDArray


Simulator = Callable[[Mapping[str, float], np.random.Generator], Mapping[str, float]]


@dataclass(frozen=True)
class SimulationResult:
    samples: Mapping[str, NDArray[np.float64]]
    mean: Mapping[str, float]
    interval_95: Mapping[str, tuple[float, float]]
    seed: int


@dataclass(frozen=True)
class ScenarioDelta:
    metric: str
    mean_b_minus_a: float
    interval_95: tuple[float, float]
    probability_b_better: float


def run_simulation(
    simulator: Simulator,
    parameters: Mapping[str, float],
    *,
    replications: int,
    seed: int,
) -> SimulationResult:
    """Run independent child streams and require a stable finite output schema."""
    if replications < 2:
        raise ValueError("replications must be at least 2 to quantify uncertainty")
    child_seeds = np.random.SeedSequence(seed).spawn(replications)
    rows: list[Mapping[str, float]] = []
    expected_keys: set[str] | None = None
    for child_seed in child_seeds:
        row = simulator(parameters, np.random.default_rng(child_seed))
        keys = set(row)
        expected_keys = keys if expected_keys is None else expected_keys
        if not keys or keys != expected_keys:
            raise ValueError("simulator output keys changed between replications")
        if any(not np.isfinite(float(value)) for value in row.values()):
            raise ValueError("simulator returned a missing or infinite metric")
        rows.append(row)

    samples = {
        key: np.asarray([float(row[key]) for row in rows], dtype=float)
        for key in sorted(expected_keys or set())
    }
    mean = {key: float(values.mean()) for key, values in samples.items()}
    intervals = {
        key: tuple(float(v) for v in np.quantile(values, [0.025, 0.975]))
        for key, values in samples.items()
    }
    return SimulationResult(samples, mean, intervals, seed)


def compare_scenarios(
    simulator: Simulator,
    scenario_a: Mapping[str, float],
    scenario_b: Mapping[str, float],
    *,
    metric: str,
    replications: int,
    seed: int,
    larger_is_better: bool = True,
) -> ScenarioDelta:
    """Use common random numbers so each A/B pair sees the same random stream."""
    if replications < 2:
        raise ValueError("replications must be at least 2")
    deltas = []
    for child_seed in np.random.SeedSequence(seed).spawn(replications):
        a = simulator(scenario_a, np.random.default_rng(child_seed))
        b = simulator(scenario_b, np.random.default_rng(child_seed))
        if metric not in a or metric not in b:
            raise KeyError(f"metric {metric!r} is missing from a simulator output")
        delta = float(b[metric]) - float(a[metric])
        if not np.isfinite(delta):
            raise ValueError("scenario difference is non-finite")
        deltas.append(delta)
    values = np.asarray(deltas)
    favorable = values > 0 if larger_is_better else values < 0
    interval = tuple(float(v) for v in np.quantile(values, [0.025, 0.975]))
    return ScenarioDelta(metric, float(values.mean()), interval, float(favorable.mean()))


def _smoke_test() -> None:
    def inventory_policy(params: Mapping[str, float], rng: np.random.Generator) -> Mapping[str, float]:
        demand = rng.normal(params["mean_demand"], 2.0)
        sold = min(params["capacity"], max(0.0, demand))
        return {"profit": 5.0 * sold - 1.0 * params["capacity"]}

    result = run_simulation(
        inventory_policy, {"mean_demand": 10.0, "capacity": 11.0}, replications=100, seed=8
    )
    delta = compare_scenarios(
        inventory_policy,
        {"mean_demand": 10.0, "capacity": 9.0},
        {"mean_demand": 10.0, "capacity": 11.0},
        metric="profit",
        replications=100,
        seed=8,
    )
    assert "profit" in result.samples and np.isfinite(delta.mean_b_minus_a)


if __name__ == "__main__":
    _smoke_test()
    print("simulation skeleton: OK")
