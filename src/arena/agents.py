"""Season-1 contestants: benchmark, cash, momentum, VWAP-reversion.

Agents see a MarketView (past only) and their own portfolio; they return orders
as equity fractions. Parameters live in dataclasses — that is the entire surface
the Gym's Optuna search is allowed to touch (ADR-002).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .bars import MarketView


@dataclass(frozen=True)
class Order:
    symbol: str
    side: str  # "buy" | "sell"
    fraction: float  # of current equity (buy) or of position (sell, 1.0 = close)
    reason: str = ""


@dataclass
class PortfolioView:
    cash: float
    equity: float
    positions: dict[str, float]  # symbol -> qty
    entry_price: dict[str, float]
    peak_price: dict[str, float]


class Agent:
    name = "agent"
    flatten_eod = True

    def decide(self, view: MarketView, portfolio: PortfolioView) -> list[Order]:
        raise NotImplementedError


class Cash(Agent):
    name = "cash"

    def decide(self, view, portfolio):
        return []


class Benchmark(Agent):
    """Buys the index on the first bar it sees and never lets go."""

    name = "benchmark"
    flatten_eod = False

    def __init__(self, symbol: str = "SPY"):
        self.symbol = symbol

    def decide(self, view, portfolio):
        if self.symbol not in portfolio.positions and portfolio.cash > 0:
            return [Order(self.symbol, "buy", 1.0, "buy and hold")]
        return []


@dataclass(frozen=True)
class MomentumParams:
    or_bars: int = 2  # opening-range length, in bars
    breakout: float = 0.001  # entry above OR high
    trail: float = 0.006  # trailing stop off the peak
    per_symbol_fraction: float = 0.25


class Momentum(Agent):
    """Opening-range breakout, long-only, trailing stop."""

    name = "momentum"

    def __init__(self, params: MomentumParams = MomentumParams()):
        self.p = params

    def decide(self, view, portfolio):
        orders: list[Order] = []
        p = self.p
        for symbol in view.symbols:
            price = view.price(symbol)
            if symbol in portfolio.positions:
                peak = portfolio.peak_price[symbol]
                if price < peak * (1.0 - p.trail):
                    orders.append(Order(symbol, "sell", 1.0, f"trailing stop (-{p.trail:.1%})"))
            else:
                closes = view.closes(symbol)
                if len(closes) <= p.or_bars:
                    continue
                or_high = view.highs(symbol)[: p.or_bars].max()
                if price > or_high * (1.0 + p.breakout) and portfolio.cash >= portfolio.equity * p.per_symbol_fraction:
                    orders.append(
                        Order(symbol, "buy", p.per_symbol_fraction,
                              f"breakout above opening range ({or_high:.2f})")
                    )
        return orders


@dataclass(frozen=True)
class ReversionParams:
    z_entry: float = -1.5  # buy when this many sigmas below VWAP
    z_exit: float = 0.0  # take profit at VWAP touch
    z_bail: float = -3.0  # cut when the dislocation keeps widening
    sigma_window: int = 12
    per_symbol_fraction: float = 0.25


class Reversion(Agent):
    """Fades dislocations below VWAP, long-only."""

    name = "reversao"

    def __init__(self, params: ReversionParams = ReversionParams()):
        self.p = params

    def _z(self, view: MarketView, symbol: str) -> float | None:
        closes = view.closes(symbol)
        if len(closes) < 4:
            return None
        window = closes[-self.p.sigma_window:]
        sigma = float(np.std(window))
        if sigma <= 0:
            return None
        return (float(closes[-1]) - view.vwap(symbol)) / sigma

    def decide(self, view, portfolio):
        orders: list[Order] = []
        p = self.p
        for symbol in view.symbols:
            z = self._z(view, symbol)
            if z is None:
                continue
            if symbol in portfolio.positions:
                if z >= p.z_exit:
                    orders.append(Order(symbol, "sell", 1.0, "VWAP touched — reversion complete"))
                elif z < p.z_bail:
                    orders.append(Order(symbol, "sell", 1.0, f"dislocation widened (z<{p.z_bail})"))
            elif z < p.z_entry and portfolio.cash >= portfolio.equity * p.per_symbol_fraction:
                orders.append(
                    Order(symbol, "buy", p.per_symbol_fraction,
                          f"{abs(z):.1f} sigma below VWAP — fade the move")
                )
        return orders
