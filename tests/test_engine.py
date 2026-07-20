"""Fills, costs, conservation and determinism of the executor."""

import numpy as np
import pandas as pd

from arena.agents import Agent, Benchmark, Cash, Momentum, Order, Reversion
from arena.bars import Session
from arena.engine import COST_BPS, SLIPPAGE_BPS, Portfolio, run_session
from arena.gym import CAPITAL, evaluate


def flat_session(n=10, price=100.0):
    ts = pd.date_range("2026-01-05 14:30", periods=n, freq="15min", tz="UTC")
    arr = lambda x: {"SPY": np.asarray(x, dtype=float)}  # noqa: E731
    closes = np.full(n, price)
    return Session(date="2026-01-05", symbols=("SPY",), ts=ts,
                   open=arr(closes), high=arr(closes), low=arr(closes),
                   close=arr(closes), volume=arr(np.full(n, 1000.0)))


class BuyOnceThenExit(Agent):
    name = "roundtrip"

    def decide(self, view, portfolio):
        if view.t == 1 and not portfolio.positions:
            return [Order("SPY", "buy", 0.5, "test entry")]
        if view.t == 3 and portfolio.positions:
            return [Order("SPY", "sell", 1.0, "test exit")]
        return []


def test_roundtrip_on_flat_prices_loses_exactly_the_frictions():
    session = flat_session()
    pf = {"roundtrip": Portfolio(cash=CAPITAL)}
    run_session(session, {"roundtrip": BuyOnceThenExit()}, pf, debug_checks=True)
    final = pf["roundtrip"].cash
    notional = CAPITAL * 0.5
    per_side = (COST_BPS + SLIPPAGE_BPS) / 10_000.0
    expected_loss = notional * per_side * 2
    assert abs((CAPITAL - final) - expected_loss) < notional * 1e-5
    assert not pf["roundtrip"].positions


def test_flatten_eod_forces_intraday_agents_flat():
    session = flat_session()
    pf = {"momentum": Portfolio(cash=CAPITAL)}

    class AlwaysLong(Agent):
        name = "momentum"

        def decide(self, view, portfolio):
            if not portfolio.positions:
                return [Order("SPY", "buy", 0.5, "enter")]
            return []

    run_session(session, {"momentum": AlwaysLong()}, pf, debug_checks=True)
    assert not pf["momentum"].positions


def test_benchmark_holds_overnight_and_cash_does_nothing():
    sessions = [flat_session(), flat_session()]
    agents = {"bench": Benchmark("SPY"), "cash": Cash()}
    pf = {name: Portfolio(cash=CAPITAL) for name in agents}
    for s in sessions:
        run_session(s, agents, pf, debug_checks=True)
    assert "SPY" in pf["bench"].positions  # still holding after day 2
    assert pf["cash"].cash == CAPITAL and not pf["cash"].positions


def test_evaluate_is_deterministic():
    rng = np.random.default_rng(3)
    n = 26
    ts = pd.date_range("2026-01-05 14:30", periods=n, freq="15min", tz="UTC")
    closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    arr = lambda x: {"SPY": np.asarray(x, dtype=float)}  # noqa: E731
    session = Session(date="2026-01-05", symbols=("SPY",), ts=ts,
                      open=arr(closes), high=arr(closes * 1.001), low=arr(closes * 0.999),
                      close=arr(closes), volume=arr(np.full(n, 1000.0)))
    a = evaluate(Momentum(), [session])
    b = evaluate(Momentum(), [session])
    assert a == b
    c = evaluate(Reversion(), [session])
    assert c == evaluate(Reversion(), [session])
