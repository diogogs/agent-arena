# ADR-001: League format, paper-only discipline, and honesty rules

Date: 2026-07-20 · Status: accepted

## Context

A single trading agent evaluated on P&L alone cannot be judged in a useful
timeframe (daily decisions need years for significance) and invites backtest
overfitting. The author's goals are learning, agent engineering with rigorous
evaluation, and a public track record — explicitly NOT alpha.

## Decision

1. **League, not lone agent**: 3-4 simple, transparent trading philosophies run
   twin portfolios simultaneously; buy-and-hold SPY and flat cash are full
   contestants. The public question is comparative ("which decision style loses
   least to doing nothing?") — answerable within one season.
2. **Intraday, not HFT**: decisions every 15-30 minutes during the US session.
   Rationale: hundreds of trades/month give statistical signal in weeks, and
   the product stays alive to watch — while remaining feasible on free data
   (Alpaca IEX) and free scheduling (cron-job.org -> Actions dispatch).
3. **Forward paper trading only**; no backtest-optimized parameters presented as
   results. Any tuning happens before a season and is frozen in the
   pre-registration commit.
4. **Pre-registered go/no-go** for ever discussing real money: beat the
   benchmark net of costs with bootstrap 95% CI over a full season while
   respecting the drawdown limit. Expected outcome: no-go — which is the
   publishable conclusion, not a failure.
5. **Own execution simulator** (fills at observed price + slippage + >=2 bps per
   side), transparent and unit-tested, instead of juggling broker paper
   accounts per agent. Alpaca supplies data; fills are simulated identically
   for all contestants.
6. **Season 1 lineup**: benchmark, cash, opening-range-breakout momentum,
   VWAP-reversion. The LLM is the league COMMENTATOR (writes the daily recap;
   does not trade) — cheap, didactic, and promotable to trader in season 2
   with the league history as context. Max 4 traders per season.

## Consequences

- The founding synthetic-day trial already delivered the didactic core: the
  reversion agent made 96 round-trips in one day and finished last — rotation
  cost is a first-class adversary and is displayed as such in the arena.
- IEX-only data means approximate fills vs consolidated tape; documented on the
  public site.
- Statistical honesty limits headline claims to benchmark-relative statements
  with intervals; single-day narratives are entertainment, labeled as such.
