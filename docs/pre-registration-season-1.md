# Pre-registration — Season 1

Committed 2026-07-20, BEFORE the season's first matchday. This document is
immutable: amendments may only be APPENDED as dated sections explaining what
changed and why — the original text is never edited (charter rule 3).

## Season

- **Start**: first US session on or after **2026-07-21**. **Length: 60
  matchdays** (~3 calendar months). Matchdays follow the NYSE calendar.
- Every portfolio resets to **100,000 virtual EUR** at season start. Season 0
  (pre-season, 2026-07-20) results are testing artifacts and carry no claims.

## Lineup and frozen parameters

| Agent | Implementation | Generation at kickoff |
|---|---|---|
| benchmark | Buy & hold SPY from first bar | static |
| cash | Holds cash | static |
| momentum | Opening-range breakout + trailing stop | **momentum-g001** |
| reversao | VWAP-dislocation fade | **reversao-g001** |

Generation parameters are exactly those in `data/registry/generations.jsonl`
at this commit. Long-only, no leverage, max 34% of equity per symbol,
intraday agents flat overnight. Universe: SPY, QQQ, AAPL, MSFT, NVDA, TSLA.
Costs: 2 bps commission + 1 bp slippage per side. Data: yfinance 15m bars
(completed bars only); Alpaca IEX becomes the source only on sustained
yfinance failure (switch would be announced in an appended amendment).

## Promotion rule (the learning loop, ADR-002)

- The Gym may train new generations at any time (walk-forward only; training
  data must END before the promotion date).
- A new generation may replace the incumbent only **on a Monday before the
  open**, at most once per agent per week, and only if its **validation**
  `vs_benchmark` exceeds the incumbent generation's validation `vs_benchmark`.
- Every promotion is recorded insert-only (registry + ledger) and the season
  table tracks the agent (franchise) continuously, while per-generation live
  records stay separable.

## Go / no-go criteria for ever DISCUSSING real money

Evaluated once, at season end, per agent. ALL must hold:

1. Season net P&L (costs included) **greater than the benchmark's** over the
   same matchdays;
2. Bootstrap 95% CI (10,000 resamples of daily P&L differences vs benchmark)
   with **lower bound above zero**;
3. Max drawdown never below **−10%**;
4. At least **40 matchdays** participated.

**Expected outcome, stated in advance: no agent qualifies.** That result is
the publishable conclusion of season 1, not a failure. Qualification triggers
a discussion, not deployment.

## Reporting

- Per matchday: automatic (ledger + site).
- **Mid-season report after matchday 30**: per-agent metrics with bootstrap
  CIs, gym-vs-live gap per generation, costs decomposition.
- Season write-up at the end: the same, plus the generational curve and
  everything that failed.

## Not investment advice

This is a public engineering and learning experiment with virtual money.
Nothing here is investment advice or a solicitation of any kind.

---

## Amendments — 2026-07-20, BEFORE the season's first matchday

Grounds: the pre-season report (docs/data/preseason.json, published on the
site). All amendments appended per this document's own rule; the original text
above stands unedited.

**Amendment 1 — promotion gate strengthened.** The stability tournament showed
single-split validation is window luck (both agents' six-window validation
spreads straddle zero). The promotion criterion becomes: the challenger is the
final-window generation of a six-window rolling tournament, and it is promoted
only if the tournament MEDIAN of validation vs_benchmark is (a) positive and
(b) strictly above the incumbent's score (its own tournament median, or its
single-split validation for the g001 kickoff generations). Monday-only timing
and once-per-agent-per-week are unchanged.

**Amendment 2 — tradable universe of the intraday traders.** Trade-level
decomposition showed the entire momentum edge lives in the two high-volatility
names (NVDA +2,665, TSLA +3,546 over 60 sessions) while SPY/QQQ/AAPL/MSFT
contribute noise that pays costs. Momentum and Reversão now trade ONLY NVDA
and TSLA. The data universe, the benchmark (SPY buy & hold) and the cost model
are unchanged.

**Amendment 3 — turnover penalty in the training objective.** Reversão's costs
consumed 81% of its gross edge. The Gym's optimization objective becomes
`vs_benchmark − costs_paid` (costs double-counted as a regularizer), so
generations learn to rotate less. Arena accounting is unchanged — this only
changes what the agents optimize for in training.

**Declared for season 1.5 (implementation to follow, entry via a future
dated amendment on a Monday):** two new contestants within the 4-trader cap,
addressing the structural finding that flat-overnight agents forfeit the
equity risk premium (two-year friendly: benchmark +69,915 vs momentum +0):
a multi-day SWING trend follower, and a VOLATILITY-TARGETED index holder
(SPY scaled by inverse realized volatility). Both will carry positions
overnight, be trained on the two-year 1h archive, and pass the same
promotion gate before fielding.
