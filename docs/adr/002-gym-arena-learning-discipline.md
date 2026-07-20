# ADR-002: Gym/Arena split — fast historical training, slow live exam

Date: 2026-07-20 · Status: accepted

## Context

ADR-001's "no backtest-optimized parameters" was overcautious as stated: waiting
for live seasons to learn would take years to produce anything useful (author's
objection, correct). The real enemy is lookahead and overfitting theater, not
historical data. The author also deprioritized the LLM commentator: not on the
critical path.

## Decision

1. **The Gym**: a point-in-time simulator replaying historical intraday bars.
   Agents receive ONLY the data window ending at bar t — no-lookahead is
   enforced by the engine's interface, not by convention, and covered by tests
   (an agent attempting to peek cannot; a synthetic future-leak agent must be
   undetectable in-interface and is used to verify the harness).
2. **Learning lives in the Gym**: parameter search (Optuna) under walk-forward
   discipline — optimize on a training window, evaluate on a later validation
   window the search never touched, roll forward. Every generation reports
   three numbers: train / validation / live. The train-vs-live gap is a
   first-class public metric.
3. **The Arena is the exam, not the classroom**: live paper trading with
   real-time data. Generations are PROMOTED from Gym to Arena at most once per
   week (cadence adjustable, pre-registered), insert-only registry of which
   generation traded when. Per-generation live track records stay separate.
4. **Matchdays (jornadas)**: each live session is a matchday with its own
   result; the season table accumulates; any past matchday is replayable in
   the arena UI. Data model: season -> matchday -> generation -> decisions/trades.
5. **The generational curve** — "does each generation lose less to the
   benchmark, live?" — is the project's long-horizon headline, now updating
   per training cycle rather than per quarter.
6. **LLM deprioritized**: commentator/coach moved to backlog (post season 1);
   daily recaps can be templated text at zero cost.

## Consequences

- Data dependency: free historical minute bars (Alpaca IEX history; Polygon
  free ~2y as alternative; yfinance 60d as fallback only) — verified and
  cached locally in J2 before anything else is built on top.
- Expected and embraced: gym results will flatter, live will humble; the gap
  is content, not embarrassment.
- Go/no-go (ADR-001) unchanged and applies to LIVE results only.
