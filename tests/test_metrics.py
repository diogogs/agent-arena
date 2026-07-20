"""The bootstrap layer behaves like statistics, deterministically."""

import numpy as np

from arena.metrics import bootstrap_ci, daily_diffs


def test_ci_is_deterministic_and_brackets_the_mean():
    rng = np.random.default_rng(0)
    diffs = rng.normal(50, 200, 60)
    a = bootstrap_ci(diffs)
    b = bootstrap_ci(diffs)
    assert a == b
    lo, mean, hi = a
    assert lo < mean < hi
    assert abs(mean - diffs.mean()) < 1e-9


def test_clearly_positive_series_excludes_zero():
    rng = np.random.default_rng(1)
    diffs = rng.normal(300, 50, 60)  # strong, consistent edge
    lo, _, _ = bootstrap_ci(diffs)
    assert lo > 0


def test_noisy_series_includes_zero():
    rng = np.random.default_rng(2)
    diffs = rng.normal(10, 500, 12)  # tiny edge, huge noise, few days
    lo, _, hi = bootstrap_ci(diffs)
    assert lo < 0 < hi


def test_daily_diffs_extracts_agent_minus_benchmark():
    matchdays = [
        {"day_pnl": {"momentum": 120.0, "benchmark": 100.0}},
        {"day_pnl": {"momentum": -50.0, "benchmark": 25.0}},
    ]
    diffs = daily_diffs(matchdays, "momentum")
    assert diffs.tolist() == [20.0, -75.0]
