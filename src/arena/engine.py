"""The execution simulator: one portfolio per agent, fills at the observed close
plus slippage, costs charged per side. Transparent, deterministic, unit-tested —
identical treatment for every contestant (ADR-001/002).

Conservation invariant (asserted in debug runs and tests): at every bar,
equity == cash + sum(qty * price) and every euro of cost is accounted in
`costs_paid`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .agents import Agent, Order, PortfolioView
from .bars import MarketView, Session

COST_BPS = 2.0  # per side, charter minimum
SLIPPAGE_BPS = 1.0  # adverse move applied to fills


@dataclass
class Trade:
    session: str
    bar: int
    agent: str
    symbol: str
    side: str
    qty: float
    price: float  # fill price incl. slippage
    cost: float
    reason: str


@dataclass
class Portfolio:
    cash: float
    positions: dict[str, float] = field(default_factory=dict)
    entry_price: dict[str, float] = field(default_factory=dict)
    peak_price: dict[str, float] = field(default_factory=dict)
    costs_paid: float = 0.0

    def equity(self, prices: dict[str, float]) -> float:
        return self.cash + sum(qty * prices[s] for s, qty in self.positions.items())


@dataclass
class AgentDayResult:
    equity_curve: list[float]
    trades: list[Trade]


def _fill(portfolio: Portfolio, order: Order, price: float, equity: float,
          session: str, bar: int, agent: str) -> Trade | None:
    if order.side == "buy":
        # the fee must fit inside available cash: cap the notional accordingly
        affordable = portfolio.cash / (1 + COST_BPS / 10_000.0)
        notional = min(equity * order.fraction, affordable)
        if notional <= 1e-9:
            return None
        fill_price = price * (1 + SLIPPAGE_BPS / 10_000.0)
        qty = notional / fill_price
        fee = notional * COST_BPS / 10_000.0
        portfolio.cash -= notional + fee
        portfolio.positions[order.symbol] = portfolio.positions.get(order.symbol, 0.0) + qty
        portfolio.entry_price[order.symbol] = fill_price
        portfolio.peak_price[order.symbol] = fill_price
        portfolio.costs_paid += fee + notional * SLIPPAGE_BPS / 10_000.0
        return Trade(session, bar, agent, order.symbol, "buy", qty, fill_price, fee, order.reason)
    qty_held = portfolio.positions.get(order.symbol, 0.0)
    qty = qty_held * order.fraction
    if qty <= 0:
        return None
    fill_price = price * (1 - SLIPPAGE_BPS / 10_000.0)
    notional = qty * fill_price
    fee = notional * COST_BPS / 10_000.0
    portfolio.cash += notional - fee
    portfolio.costs_paid += fee + qty * price * SLIPPAGE_BPS / 10_000.0
    remaining = qty_held - qty
    if remaining <= 1e-12:
        portfolio.positions.pop(order.symbol, None)
        portfolio.entry_price.pop(order.symbol, None)
        portfolio.peak_price.pop(order.symbol, None)
    else:
        portfolio.positions[order.symbol] = remaining
    return Trade(session, bar, agent, order.symbol, "sell", qty, fill_price, fee, order.reason)


def run_session(
    session: Session,
    agents: dict[str, Agent],
    portfolios: dict[str, Portfolio],
    debug_checks: bool = False,
) -> dict[str, AgentDayResult]:
    """Advance every agent through one day. Portfolios are carried in/out so
    multi-day runs preserve overnight holdings (benchmark) while flatten_eod
    agents are forced flat on the last bar."""
    results = {name: AgentDayResult([], []) for name in agents}
    for t in range(session.n_bars):
        view = MarketView(session, t)
        prices = {s: float(session.close[s][t]) for s in session.symbols}
        for name, agent in agents.items():
            pf = portfolios[name]
            for s in pf.positions:
                pf.peak_price[s] = max(pf.peak_price.get(s, prices[s]), prices[s])
            equity = pf.equity(prices)
            orders = list(agent.decide(view, PortfolioView(
                cash=pf.cash, equity=equity,
                positions=dict(pf.positions),
                entry_price=dict(pf.entry_price),
                peak_price=dict(pf.peak_price),
            )))
            if agent.flatten_eod and t == session.n_bars - 1:
                orders = [Order(s, "sell", 1.0, "end of session — flat overnight")
                          for s in list(pf.positions)]
            for order in orders:
                trade = _fill(pf, order, prices[order.symbol], equity,
                              session.date, t, name)
                if trade:
                    results[name].trades.append(trade)
            eq = pf.equity(prices)
            results[name].equity_curve.append(eq)
            if debug_checks:
                recomputed = pf.cash + sum(q * prices[s] for s, q in pf.positions.items())
                assert abs(recomputed - eq) < 1e-6, "conservation broken"
                assert pf.cash > -1e-6, f"negative cash for {name}"
    return results
