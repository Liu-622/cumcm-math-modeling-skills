"""Leakage-safe forecasting skeleton with a mandatory naive baseline.

Extend ``ForecastModel`` only after the series frequency, horizon and exogenous
feature availability are defined.  Do not use this template for causal claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Protocol

import numpy as np
from numpy.typing import ArrayLike, NDArray


class ForecastModel(Protocol):
    """Minimal interface: fit on the past, predict an explicit future horizon."""

    def fit(self, y: NDArray[np.float64]) -> "ForecastModel": ...

    def predict(self, horizon: int) -> NDArray[np.float64]: ...


class LastValueForecast:
    """Required baseline for many level-series forecasting tasks."""

    def fit(self, y: NDArray[np.float64]) -> "LastValueForecast":
        self.last_value = float(y[-1])
        return self

    def predict(self, horizon: int) -> NDArray[np.float64]:
        return np.full(horizon, self.last_value, dtype=float)


class LinearTrendForecast:
    """Transparent candidate; use only when a stable local trend is defensible."""

    def fit(self, y: NDArray[np.float64]) -> "LinearTrendForecast":
        self.n_obs = y.size
        self.slope, self.intercept = np.polyfit(np.arange(self.n_obs), y, 1)
        return self

    def predict(self, horizon: int) -> NDArray[np.float64]:
        future_t = np.arange(self.n_obs, self.n_obs + horizon)
        return self.intercept + self.slope * future_t


@dataclass(frozen=True)
class BacktestResult:
    actual: NDArray[np.float64]
    predicted: NDArray[np.float64]
    origins: NDArray[np.int64]
    mae: float
    rmse: float


@dataclass(frozen=True)
class ModelComparison:
    results: Mapping[str, BacktestResult]
    recommended: str
    relative_rmse_gain: float


def _series(y: ArrayLike) -> NDArray[np.float64]:
    values = np.asarray(y, dtype=float)
    if values.ndim != 1 or values.size < 3:
        raise ValueError("y must be a one-dimensional series with at least 3 observations")
    if not np.isfinite(values).all():
        raise ValueError("y contains missing or infinite values; handle them explicitly")
    return values


def rolling_origin_backtest(
    model_factory: Callable[[], ForecastModel],
    y: ArrayLike,
    *,
    min_train_size: int,
    horizon: int = 1,
    step: int = 1,
) -> BacktestResult:
    """Evaluate genuine future forecasts; a fresh model is fitted at each origin."""
    values = _series(y)
    if not 2 <= min_train_size <= values.size - horizon:
        raise ValueError("min_train_size leaves no complete test horizon")
    if horizon < 1 or step < 1:
        raise ValueError("horizon and step must be positive")

    actual, predicted, origins = [], [], []
    for origin in range(min_train_size, values.size - horizon + 1, step):
        model = model_factory().fit(values[:origin].copy())
        forecast = np.asarray(model.predict(horizon), dtype=float)
        if forecast.shape != (horizon,) or not np.isfinite(forecast).all():
            raise ValueError(f"invalid forecast at origin {origin}: expected {horizon} finite values")
        actual.extend(values[origin : origin + horizon])
        predicted.extend(forecast)
        origins.extend([origin] * horizon)

    y_true = np.asarray(actual, dtype=float)
    y_pred = np.asarray(predicted, dtype=float)
    errors = y_pred - y_true
    return BacktestResult(
        actual=y_true,
        predicted=y_pred,
        origins=np.asarray(origins, dtype=np.int64),
        mae=float(np.mean(np.abs(errors))),
        rmse=float(np.sqrt(np.mean(errors**2))),
    )


def compare_forecasters(
    candidates: Mapping[str, Callable[[], ForecastModel]],
    y: ArrayLike,
    *,
    baseline_name: str,
    min_train_size: int,
    horizon: int = 1,
    minimum_relative_gain: float = 0.02,
) -> ModelComparison:
    """Prefer the baseline unless another candidate clears a declared gain threshold."""
    if baseline_name not in candidates:
        raise ValueError("candidates must include the declared baseline")
    results = {
        name: rolling_origin_backtest(factory, y, min_train_size=min_train_size, horizon=horizon)
        for name, factory in candidates.items()
    }
    baseline_rmse = results[baseline_name].rmse
    best_name = min(results, key=lambda name: results[name].rmse)
    gain = (baseline_rmse - results[best_name].rmse) / max(baseline_rmse, np.finfo(float).eps)
    recommended = best_name if gain >= minimum_relative_gain else baseline_name
    return ModelComparison(results=results, recommended=recommended, relative_rmse_gain=float(gain))


def _smoke_test() -> None:
    y = 3.0 + 0.7 * np.arange(40)
    report = compare_forecasters(
        {"naive": LastValueForecast, "linear_trend": LinearTrendForecast},
        y,
        baseline_name="naive",
        min_train_size=15,
    )
    assert report.recommended == "linear_trend"
    assert report.results["linear_trend"].rmse < 1e-9


if __name__ == "__main__":
    _smoke_test()
    print("prediction skeleton: OK")
