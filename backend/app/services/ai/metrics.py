"""Dependency-free evaluation helpers (numpy only) used by training and tests."""
from __future__ import annotations

import numpy as np


def roc_auc(y: np.ndarray, s: np.ndarray) -> float:
    y, s = np.asarray(y).astype(int), np.asarray(s, dtype=float)
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    # Mann-Whitney U with average ranks for ties
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    allv = np.concatenate([pos, neg])[order]
    ranks = np.empty(len(allv))
    i = 0
    while i < len(allv):
        j = i
        while j + 1 < len(allv) and allv[j + 1] == allv[i]:
            j += 1
        ranks[i:j + 1] = (i + j) / 2 + 1
        i = j + 1
    r = np.empty(len(allv))
    r[order] = ranks
    return float((r[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def pr_auc(y: np.ndarray, s: np.ndarray) -> float:
    """Average precision (area under the precision-recall curve, step-wise)."""
    y, s = np.asarray(y).astype(int), np.asarray(s, dtype=float)
    if y.sum() == 0:
        return float("nan")
    order = np.argsort(-s, kind="mergesort")
    y = y[order]
    tp = np.cumsum(y)
    precision = tp / np.arange(1, len(y) + 1)
    return float((precision * y).sum() / y.sum())


def binary_metrics(y, s, threshold: float) -> dict:
    y, s = np.asarray(y).astype(int), np.asarray(s, dtype=float)
    pred = (s >= threshold).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    spec = tn / (tn + fp) if tn + fp else 0.0
    return {
        "threshold": float(threshold),
        "accuracy": round((tp + tn) / max(1, len(y)), 4),
        "balanced_accuracy": round((rec + spec) / 2, 4),
        "precision": round(prec, 4), "recall": round(rec, 4), "specificity": round(spec, 4), "f1": round(f1, 4),
        "roc_auc": round(roc_auc(y, s), 4), "pr_auc": round(pr_auc(y, s), 4),
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
        "confusion_matrix_note": "rows=actual (real, manipulated), cols=predicted; positive class = manipulated",
    }


def expected_calibration_error(y, p, bins: int = 10) -> float:
    y, p = np.asarray(y).astype(int), np.asarray(p, dtype=float)
    edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & ((p < hi) if hi < 1 else (p <= hi))
        if m.any():
            ece += m.mean() * abs(p[m].mean() - y[m].mean())
    return round(float(ece), 4)


def fit_temperature(logits, y, grid=None) -> float:
    """Temperature scaling (Guo et al., 2017) fitted by NLL grid search on validation logits."""
    logits, y = np.asarray(logits, dtype=float), np.asarray(y, dtype=float)
    grid = grid if grid is not None else np.exp(np.linspace(np.log(0.25), np.log(8.0), 200))
    best_t, best_nll = 1.0, float("inf")
    for t in grid:
        p = 1 / (1 + np.exp(-logits / t))
        p = np.clip(p, 1e-7, 1 - 1e-7)
        nll = -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
        if nll < best_nll:
            best_nll, best_t = nll, float(t)
    return round(best_t, 4)


def aggregate_scores(scores: list[float], rule: str = "mean") -> float | None:
    """Documented aggregation of per-face / per-frame scores."""
    if not scores:
        return None
    arr = np.asarray(scores, dtype=float)
    if rule == "mean":
        return float(arr.mean())
    if rule == "median":
        return float(np.median(arr))
    if rule == "max":
        return float(arr.max())
    raise ValueError(f"unknown aggregation rule {rule}")


def verdict_for(score: float | None, threshold: float, margin: float = 0.10) -> str:
    """Map a calibrated score to an AI result label.

    Scores within +/- `margin` of the threshold are reported as INCONCLUSIVE rather than
    forcing a binary call.
    """
    if score is None:
        return "INCONCLUSIVE"
    if score >= min(0.99, threshold + margin):
        return "LIKELY_MANIPULATED"
    if score <= max(0.01, threshold - margin):
        return "LOW_MANIPULATION_SIGNAL"
    return "INCONCLUSIVE"
