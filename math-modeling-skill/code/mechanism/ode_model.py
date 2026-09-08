"""ODE simulation, parameter fitting and local-sensitivity skeleton.

Write the right-hand side from a documented mechanism and unit balance.  A
good numerical fit alone does not validate the mechanism or identify causality.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.integrate import solve_ivp
from scipy.optimize import least_squares


RightHandSide = Callable[
    [float, NDArray[np.float64], NDArray[np.float64]], NDArray[np.float64]
]


@dataclass(frozen=True)
class ODEFit:
    parameters: NDArray[np.float64]
    fitted_states: NDArray[np.float64]
    residuals: NDArray[np.float64]
    rmse: float
    optimizer_success: bool
    message: str


def _times(values: ArrayLike) -> NDArray[np.float64]:
    times = np.asarray(values, dtype=float)
    if times.ndim != 1 or times.size < 2 or not np.isfinite(times).all():
        raise ValueError("times must contain at least two finite values")
    if (np.diff(times) <= 0).any():
        raise ValueError("times must be strictly increasing")
    return times


def simulate_ode(
    rhs: RightHandSide,
    initial_state: ArrayLike,
    times: ArrayLike,
    parameters: ArrayLike,
) -> NDArray[np.float64]:
    """Return shape (n_times, n_states), failing on integration problems."""
    t = _times(times)
    y0 = np.asarray(initial_state, dtype=float)
    theta = np.asarray(parameters, dtype=float)
    if y0.ndim != 1 or theta.ndim != 1 or not np.isfinite(y0).all() or not np.isfinite(theta).all():
        raise ValueError("initial_state and parameters must be finite vectors")
    solution = solve_ivp(
        lambda time, state: np.asarray(rhs(time, state, theta), dtype=float),
        (float(t[0]), float(t[-1])),
        y0,
        t_eval=t,
        rtol=1e-7,
        atol=1e-9,
    )
    if not solution.success or solution.y.shape != (y0.size, t.size):
        raise RuntimeError(f"ODE integration failed: {solution.message}")
    states = solution.y.T
    if not np.isfinite(states).all():
        raise RuntimeError("ODE integration produced non-finite states")
    return states


def fit_parameters(
    rhs: RightHandSide,
    initial_state: ArrayLike,
    times: ArrayLike,
    observations: ArrayLike,
    initial_parameters: ArrayLike,
    bounds: tuple[ArrayLike, ArrayLike],
    *,
    observation_scale: ArrayLike | None = None,
) -> ODEFit:
    """Fit parameters; inspect sensitivity/identifiability before interpreting them."""
    t = _times(times)
    y0 = np.asarray(initial_state, dtype=float)
    observed = np.asarray(observations, dtype=float)
    theta0 = np.asarray(initial_parameters, dtype=float)
    lower, upper = (np.asarray(part, dtype=float) for part in bounds)
    if observed.shape != (t.size, y0.size) or not np.isfinite(observed).all():
        raise ValueError("observations must have shape (n_times, n_states) and be finite")
    if theta0.ndim != 1 or lower.shape != theta0.shape or upper.shape != theta0.shape:
        raise ValueError("initial parameters and bounds must have matching vector shapes")
    scale = np.ones(y0.size) if observation_scale is None else np.asarray(observation_scale, dtype=float)
    if scale.shape != (y0.size,) or (scale <= 0).any() or not np.isfinite(scale).all():
        raise ValueError("observation_scale must be one positive finite value per state")

    def residual(theta: NDArray[np.float64]) -> NDArray[np.float64]:
        return ((simulate_ode(rhs, y0, t, theta) - observed) / scale).ravel()

    raw = least_squares(residual, theta0, bounds=(lower, upper), max_nfev=2_000)
    fitted = simulate_ode(rhs, y0, t, raw.x)
    errors = fitted - observed
    return ODEFit(
        parameters=np.asarray(raw.x),
        fitted_states=fitted,
        residuals=errors,
        rmse=float(np.sqrt(np.mean(errors**2))),
        optimizer_success=bool(raw.success),
        message=str(raw.message),
    )


def local_parameter_sensitivity(
    rhs: RightHandSide,
    initial_state: ArrayLike,
    times: ArrayLike,
    parameters: ArrayLike,
    *,
    relative_step: float = 1e-4,
) -> NDArray[np.float64]:
    """Return d(state)/d(parameter) with shape (n_parameters, n_times, n_states)."""
    theta = np.asarray(parameters, dtype=float)
    if theta.ndim != 1 or relative_step <= 0:
        raise ValueError("parameters must be a vector and relative_step positive")
    derivatives = []
    for index, value in enumerate(theta):
        step = relative_step * max(abs(float(value)), 1.0)
        plus, minus = theta.copy(), theta.copy()
        plus[index] += step
        minus[index] -= step
        derivatives.append(
            (simulate_ode(rhs, initial_state, times, plus) - simulate_ode(rhs, initial_state, times, minus))
            / (2 * step)
        )
    return np.asarray(derivatives)


def _smoke_test() -> None:
    def logistic(_t: float, state: NDArray[np.float64], theta: NDArray[np.float64]) -> NDArray[np.float64]:
        growth, capacity = theta
        return np.asarray([growth * state[0] * (1.0 - state[0] / capacity)])

    times = np.linspace(0, 10, 31)
    observed = simulate_ode(logistic, [2.0], times, [0.4, 20.0])
    fit = fit_parameters(logistic, [2.0], times, observed, [0.3, 18.0], ([0.01, 5.0], [2.0, 50.0]))
    sensitivity = local_parameter_sensitivity(logistic, [2.0], times, fit.parameters)
    assert fit.optimizer_success and fit.rmse < 1e-5
    assert sensitivity.shape == (2, times.size, 1)


if __name__ == "__main__":
    _smoke_test()
    print("mechanism skeleton: OK")
