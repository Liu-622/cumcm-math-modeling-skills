"""Classifier comparison skeleton with explicit splits and a dummy baseline.

Pass preprocessing and the estimator together in an sklearn ``Pipeline`` so
each fold learns transformations from training data only.  For temporal,
spatial or grouped samples, construct matching splits outside this function.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import numpy as np
from numpy.typing import ArrayLike, NDArray
from sklearn.base import BaseEstimator, clone
from sklearn.metrics import accuracy_score, balanced_accuracy_score


@dataclass(frozen=True)
class CandidateReport:
    accuracy_by_fold: NDArray[np.float64]
    balanced_accuracy_by_fold: NDArray[np.float64]

    @property
    def mean_balanced_accuracy(self) -> float:
        return float(np.mean(self.balanced_accuracy_by_fold))


@dataclass(frozen=True)
class ClassifierComparison:
    reports: Mapping[str, CandidateReport]
    recommended: str
    gain_over_baseline: float


def compare_classifiers(
    features: ArrayLike,
    target: ArrayLike,
    candidates: Mapping[str, BaseEstimator],
    splits: Iterable[tuple[ArrayLike, ArrayLike]],
    *,
    baseline_name: str,
    minimum_gain: float = 0.01,
) -> ClassifierComparison:
    """Evaluate fixed folds and retain the baseline unless gain clears a threshold."""
    x = np.asarray(features, dtype=float)
    y = np.asarray(target)
    if x.ndim != 2 or y.ndim != 1 or x.shape[0] != y.size or y.size < 4:
        raise ValueError("features must be 2D and aligned with a one-dimensional target")
    if not np.isfinite(x).all():
        raise ValueError("features contain missing/infinite values; handle them inside a Pipeline")
    if np.unique(y).size < 2:
        raise ValueError("classification needs at least two target classes")
    if baseline_name not in candidates:
        raise ValueError("include an explicit dummy/majority baseline")

    fixed_splits = [
        (np.asarray(train, dtype=int), np.asarray(test, dtype=int)) for train, test in splits
    ]
    if not fixed_splits:
        raise ValueError("at least one train/test split is required")
    for train, test in fixed_splits:
        if train.size == 0 or test.size == 0 or np.intersect1d(train, test).size:
            raise ValueError("each split needs non-empty, disjoint train and test indices")
        if min(train.min(), test.min()) < 0 or max(train.max(), test.max()) >= y.size:
            raise ValueError("split index is out of range")

    reports: dict[str, CandidateReport] = {}
    for name, estimator in candidates.items():
        accuracy, balanced = [], []
        for train, test in fixed_splits:
            model = clone(estimator).fit(x[train], y[train])
            prediction = model.predict(x[test])
            accuracy.append(accuracy_score(y[test], prediction))
            balanced.append(balanced_accuracy_score(y[test], prediction))
        reports[name] = CandidateReport(np.asarray(accuracy), np.asarray(balanced))

    baseline_score = reports[baseline_name].mean_balanced_accuracy
    best_name = max(reports, key=lambda name: reports[name].mean_balanced_accuracy)
    gain = reports[best_name].mean_balanced_accuracy - baseline_score
    recommended = best_name if gain >= minimum_gain else baseline_name
    return ClassifierComparison(reports, recommended, float(gain))


def _smoke_test() -> None:
    from sklearn.dummy import DummyClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    rng = np.random.default_rng(3)
    x = rng.normal(size=(100, 2))
    y = (x[:, 0] + 0.5 * x[:, 1] > 0).astype(int)
    splitter = StratifiedKFold(4, shuffle=True, random_state=2)
    result = compare_classifiers(
        x,
        y,
        {
            "majority": DummyClassifier(strategy="most_frequent"),
            "logistic": make_pipeline(StandardScaler(), LogisticRegression(max_iter=500)),
        },
        splitter.split(x, y),
        baseline_name="majority",
    )
    assert result.recommended == "logistic"


if __name__ == "__main__":
    _smoke_test()
    print("machine-learning skeleton: OK")
