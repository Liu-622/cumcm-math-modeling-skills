"""Continuous constrained-optimization skeleton with auditable constraints.

Residuals use the convention ``residual(x) >= 0``.  Use a MILP/CP solver for
integer, routing or logical decisions instead of rounding this solution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import minimize


Objective = Callable[[NDArray[np.float64]], float]
Residual = Callable[[NDArray[np.float64]], float]


@dataclass(frozen=True)
class Constraint:
    name: str
    residual: Residual
    source: str  # Trace this to the problem statement, data, or a declared assumption.


@dataclass(frozen=True)
class OptimizationSpec:
    objective: Objective
    bounds: Sequence[tuple[float | None, float | None]]
    constraints: Sequence[Constraint]
    objective_meaning: str


@dataclass(frozen=True)
class OptimizationResult:
    x: NDArray[np.float64]
    objective: float
    feasible: bool
    max_violation: float
    solver_success: bool
    message: str


def _candidate(x: ArrayLike, dimension: int) -> NDArray[np.float64]:
    values = np.asarray(x, dtype=float)
    if values.shape != (dimension,) or not np.isfinite(values).all():
        raise ValueError(f"candidate must contain {dimension} finite values")
    return values


def constraint_violations(spec: OptimizationSpec, x: ArrayLike) -> dict[str, float]:
    """Return positive violation magnitudes for bounds and named constraints."""
    values = _candidate(x, len(spec.bounds))
    violations: dict[str, float] = {}
    for i, (value, (lower, upper)) in enumerate(zip(values, spec.bounds)):
        violations[f"bound[{i}]"] = max(
            0.0,
            0.0 if lower is None else lower - value,
            0.0 if upper is None else value - upper,
        )
    for constraint in spec.constraints:
        residual = float(constraint.residual(values))
        if not np.isfinite(residual):
            raise ValueError(f"constraint {constraint.name!r} returned a non-finite residual")
        violations[constraint.name] = max(0.0, -residual)
    return violations


def solve_continuous(
    spec: OptimizationSpec,
    initial: ArrayLike,
    *,
    feasibility_tolerance: float = 1e-7,
    max_iterations: int = 2_000,
) -> OptimizationResult:
    """Solve once; for non-convex models call from documented multiple starts."""
    x0 = _candidate(initial, len(spec.bounds))
    scipy_constraints = [
        {"type": "ineq", "fun": constraint.residual} for constraint in spec.constraints
    ]
    raw = minimize(
        spec.objective,
        x0,
        method="SLSQP",
        bounds=spec.bounds,
        constraints=scipy_constraints,
        options={"maxiter": max_iterations, "ftol": 1e-10},
    )
    x = np.asarray(raw.x, dtype=float)
    violations = constraint_violations(spec, x)
    max_violation = max(violations.values(), default=0.0)
    objective = float(spec.objective(x))
    if not np.isfinite(objective):
        raise ValueError("objective returned a non-finite value at the solver output")
    return OptimizationResult(
        x=x,
        objective=objective,
        feasible=max_violation <= feasibility_tolerance,
        max_violation=float(max_violation),
        solver_success=bool(raw.success),
        message=str(raw.message),
    )


def _smoke_test() -> None:
    spec = OptimizationSpec(
        objective=lambda x: float((x[0] - 2.0) ** 2),
        bounds=[(0.0, 5.0)],
        constraints=[Constraint("minimum_service", lambda x: float(x[0] - 1.0), "test rule")],
        objective_meaning="squared deviation from target",
    )
    result = solve_continuous(spec, [1.5])
    assert result.solver_success and result.feasible
    assert abs(result.x[0] - 2.0) < 1e-5


if __name__ == "__main__":
    _smoke_test()
    print("optimization skeleton: OK")
