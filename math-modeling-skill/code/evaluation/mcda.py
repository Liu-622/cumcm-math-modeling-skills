"""Transparent TOPSIS skeleton plus weight-sensitivity diagnostics.

Use only after indicator meaning, direction and redundancy are justified.  A
ranking is not evidence that the indicator system itself is valid.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.stats import rankdata


@dataclass(frozen=True)
class MCDAResult:
    scores: NDArray[np.float64]
    ranks: NDArray[np.int64]
    weighted_matrix: NDArray[np.float64]


@dataclass(frozen=True)
class WeightSensitivity:
    top_choice_probability: NDArray[np.float64]
    mean_rank: NDArray[np.float64]
    sampled_weights: NDArray[np.float64]


def _inputs(
    matrix: ArrayLike, weights: ArrayLike, benefit: ArrayLike
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.bool_]]:
    x = np.asarray(matrix, dtype=float)
    w = np.asarray(weights, dtype=float)
    direction = np.asarray(benefit, dtype=bool)
    if x.ndim != 2 or min(x.shape) < 2 or not np.isfinite(x).all():
        raise ValueError("matrix must be a finite 2D array with at least 2 alternatives and criteria")
    if w.shape != (x.shape[1],) or direction.shape != (x.shape[1],):
        raise ValueError("weights and benefit flags must match the number of criteria")
    if (w < 0).any() or w.sum() <= 0:
        raise ValueError("weights must be non-negative with a positive sum")
    norms = np.linalg.norm(x, axis=0)
    if (norms == 0).any():
        raise ValueError("a criterion column has zero norm; remove or redefine it")
    return x, w / w.sum(), direction


def topsis(matrix: ArrayLike, weights: ArrayLike, benefit: ArrayLike) -> MCDAResult:
    """Rank alternatives; ``benefit[j]=False`` marks a cost criterion."""
    x, w, direction = _inputs(matrix, weights, benefit)
    weighted = x / np.linalg.norm(x, axis=0) * w
    best = np.where(direction, weighted.max(axis=0), weighted.min(axis=0))
    worst = np.where(direction, weighted.min(axis=0), weighted.max(axis=0))
    d_best = np.linalg.norm(weighted - best, axis=1)
    d_worst = np.linalg.norm(weighted - worst, axis=1)
    denominator = d_best + d_worst
    scores = np.divide(d_worst, denominator, out=np.full_like(d_worst, 0.5), where=denominator > 0)
    ranks = rankdata(-scores, method="min").astype(np.int64)
    return MCDAResult(scores=scores, ranks=ranks, weighted_matrix=weighted)


def criterion_redundancy(matrix: ArrayLike, *, threshold: float = 0.95) -> list[tuple[int, int, float]]:
    """Flag highly correlated criteria for human review; do not auto-delete them."""
    x = np.asarray(matrix, dtype=float)
    if x.ndim != 2 or not np.isfinite(x).all():
        raise ValueError("matrix must be finite and two-dimensional")
    corr = np.corrcoef(x, rowvar=False)
    return [
        (i, j, float(corr[i, j]))
        for i in range(corr.shape[0])
        for j in range(i + 1, corr.shape[1])
        if np.isfinite(corr[i, j]) and abs(corr[i, j]) >= threshold
    ]


def weight_sensitivity(
    matrix: ArrayLike,
    base_weights: ArrayLike,
    benefit: ArrayLike,
    *,
    samples: int = 1_000,
    concentration: float = 100.0,
    seed: int = 0,
) -> WeightSensitivity:
    """Perturb positive weights with a Dirichlet distribution and track rank stability."""
    x, w, direction = _inputs(matrix, base_weights, benefit)
    if (w <= 0).any():
        raise ValueError("Dirichlet sensitivity requires strictly positive base weights")
    if samples < 2 or concentration <= 0:
        raise ValueError("samples must exceed 1 and concentration must be positive")
    draws = np.random.default_rng(seed).dirichlet(w * concentration, size=samples)
    ranks = np.vstack([topsis(x, draw, direction).ranks for draw in draws])
    top_probability = np.mean(ranks == 1, axis=0)
    return WeightSensitivity(
        top_choice_probability=top_probability,
        mean_rank=np.mean(ranks, axis=0),
        sampled_weights=draws,
    )


def _smoke_test() -> None:
    matrix = [[90, 8, 30], [80, 6, 20], [70, 9, 10]]
    result = topsis(matrix, [0.4, 0.3, 0.3], [True, True, False])
    sensitivity = weight_sensitivity(matrix, [0.4, 0.3, 0.3], [True, True, False], samples=50)
    assert result.ranks.shape == (3,)
    assert np.isclose(sensitivity.top_choice_probability.sum(), 1.0)


if __name__ == "__main__":
    _smoke_test()
    print("evaluation skeleton: OK")
