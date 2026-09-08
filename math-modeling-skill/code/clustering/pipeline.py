"""K-means selection skeleton using separation, stability and minimum size.

Clustering is useful only if unlabeled heterogeneity matters to a later decision.
Profiles must be interpreted in original units before labels receive names.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

import numpy as np
from numpy.typing import ArrayLike, NDArray
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler


@dataclass(frozen=True)
class KDiagnostic:
    k: int
    silhouette: float
    stability: float
    smallest_cluster: int
    eligible: bool


@dataclass(frozen=True)
class ClusteringResult:
    labels: NDArray[np.int64]
    profiles_original_units: NDArray[np.float64]
    selected_k: int
    diagnostics: tuple[KDiagnostic, ...]


def _matrix(data: ArrayLike) -> NDArray[np.float64]:
    x = np.asarray(data, dtype=float)
    if x.ndim != 2 or x.shape[0] < 5 or x.shape[1] < 1:
        raise ValueError("data must contain at least 5 rows and 1 feature")
    if not np.isfinite(x).all():
        raise ValueError("data contains missing/infinite values; handle them explicitly")
    if (np.std(x, axis=0) == 0).any():
        raise ValueError("remove constant features before clustering")
    return x


def select_kmeans(
    data: ArrayLike,
    candidate_k: Iterable[int],
    *,
    repeats: int = 8,
    minimum_cluster_size: int = 3,
    minimum_stability: float = 0.80,
    seed: int = 0,
) -> ClusteringResult:
    """Select the best-separated k among solutions meeting declared guardrails."""
    x = _matrix(data)
    ks = sorted(set(int(k) for k in candidate_k))
    if not ks or min(ks) < 2 or max(ks) >= x.shape[0]:
        raise ValueError("candidate k values must satisfy 2 <= k < n_samples")
    if repeats < 2 or minimum_cluster_size < 1:
        raise ValueError("repeats must exceed 1 and minimum_cluster_size must be positive")

    scaled = StandardScaler().fit_transform(x)
    rng = np.random.default_rng(seed)
    diagnostics: list[KDiagnostic] = []
    best_labels_by_k: dict[int, NDArray[np.int64]] = {}

    for k in ks:
        labels_runs, inertias = [], []
        for run_seed in rng.integers(0, np.iinfo(np.int32).max, size=repeats):
            model = KMeans(n_clusters=k, n_init=10, random_state=int(run_seed)).fit(scaled)
            labels_runs.append(model.labels_.astype(np.int64))
            inertias.append(float(model.inertia_))
        best_index = int(np.argmin(inertias))
        labels = labels_runs[best_index]
        stability = float(
            np.mean([adjusted_rand_score(a, b) for a, b in combinations(labels_runs, 2)])
        )
        smallest = int(np.bincount(labels, minlength=k).min())
        separation = float(silhouette_score(scaled, labels))
        eligible = smallest >= minimum_cluster_size and stability >= minimum_stability
        diagnostics.append(KDiagnostic(k, separation, stability, smallest, eligible))
        best_labels_by_k[k] = labels

    eligible = [item for item in diagnostics if item.eligible]
    if not eligible:
        raise ValueError("no k satisfies minimum cluster size and stability; reconsider clustering")
    selected = max(eligible, key=lambda item: item.silhouette)
    labels = best_labels_by_k[selected.k]
    profiles = np.vstack([x[labels == cluster].mean(axis=0) for cluster in range(selected.k)])
    return ClusteringResult(labels, profiles, selected.k, tuple(diagnostics))


def _smoke_test() -> None:
    rng = np.random.default_rng(7)
    data = np.vstack([rng.normal(-2, 0.2, (25, 2)), rng.normal(2, 0.2, (25, 2))])
    result = select_kmeans(data, [2, 3], minimum_cluster_size=5)
    assert result.selected_k == 2
    assert result.profiles_original_units.shape == (2, 2)


if __name__ == "__main__":
    _smoke_test()
    print("clustering skeleton: OK")
