"""Scoring rules and calibration diagnostics. Inputs are always pre-match probabilities."""
from __future__ import annotations

import numpy as np

EPS = 1e-12


def brier_multiclass(probs: np.ndarray, outcomes: np.ndarray) -> float:
    """Mean over matches of sum_k (p_k - o_k)^2. probs/outcomes shape (n, k)."""
    probs, outcomes = np.atleast_2d(probs), np.atleast_2d(outcomes)
    return float(np.mean(np.sum((probs - outcomes) ** 2, axis=1)))


def brier_binary(p: np.ndarray, y: np.ndarray) -> float:
    p, y = np.asarray(p, float), np.asarray(y, float)
    return float(np.mean((p - y) ** 2))


def log_loss_multiclass(probs: np.ndarray, outcomes: np.ndarray) -> float:
    probs, outcomes = np.atleast_2d(probs), np.atleast_2d(outcomes)
    return float(-np.mean(np.sum(outcomes * np.log(np.clip(probs, EPS, 1)), axis=1)))


def log_loss_binary(p: np.ndarray, y: np.ndarray) -> float:
    p, y = np.clip(np.asarray(p, float), EPS, 1 - EPS), np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def reliability_bins(p: np.ndarray, y: np.ndarray, n_bins: int = 10) -> list[dict]:
    """Reliability-diagram data: for each probability bucket, mean forecast vs observed frequency."""
    p, y = np.asarray(p, float), np.asarray(y, float)
    edges = np.linspace(0, 1, n_bins + 1)
    out = []
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (p >= lo) & (p < hi) if i < n_bins - 1 else (p >= lo) & (p <= hi)
        n = int(mask.sum())
        out.append({
            "bin_low": float(lo), "bin_high": float(hi), "count": n,
            "mean_predicted": float(p[mask].mean()) if n else None,
            "observed_rate": float(y[mask].mean()) if n else None,
        })
    return out


def expected_calibration_error(p: np.ndarray, y: np.ndarray, n_bins: int = 10) -> float:
    bins = reliability_bins(p, y, n_bins)
    total = sum(b["count"] for b in bins)
    if total == 0:
        return float("nan")
    return float(sum(b["count"] * abs(b["mean_predicted"] - b["observed_rate"]) for b in bins if b["count"]) / total)
