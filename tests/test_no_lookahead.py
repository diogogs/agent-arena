"""The charter's core guarantee: an agent physically cannot see the future."""

import numpy as np
import pandas as pd

from arena.bars import MarketView, Session


def synthetic_session(n=20, spike_at=15):
    closes = np.full(n, 100.0)
    closes[spike_at:] = 500.0  # a future an agent would love to know about
    ts = pd.date_range("2026-01-05 14:30", periods=n, freq="15min", tz="UTC")
    arr = lambda x: {"SPY": np.asarray(x, dtype=float)}  # noqa: E731
    return Session(
        date="2026-01-05", symbols=("SPY",), ts=ts,
        open=arr(closes), high=arr(closes + 1), low=arr(closes - 1),
        close=arr(closes), volume=arr(np.full(n, 1000.0)),
    )


def test_view_holds_only_the_past():
    session = synthetic_session()
    for t in range(session.n_bars):
        view = MarketView(session, t)
        assert len(view.closes("SPY")) == t + 1
        # before the spike bar, the spike is invisible everywhere in the view
        if t < 15:
            assert view.closes("SPY").max() < 500
            assert view.highs("SPY").max() < 500


def test_view_arrays_are_copies():
    session = synthetic_session()
    view = MarketView(session, 5)
    view.closes("SPY")[:] = -1.0  # vandalize the returned array
    assert session.close["SPY"][0] == 100.0  # session untouched
    assert MarketView(session, 5).closes("SPY")[0] == 100.0


def test_view_exposes_no_session_reference():
    view = MarketView(synthetic_session(), 3)
    leaked = [a for a in vars(view).values() if isinstance(a, Session)]
    assert not leaked, "MarketView must not carry the full Session"
