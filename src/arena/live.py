"""The live Arena cycle (J3): called every 15 minutes of the US session.

Each cycle: refresh archives -> build today's session from COMPLETED bars only
-> advance every agent through the bars not yet processed -> append to the
insert-only ledgers -> close the matchday when the last bar is in. Running a
cycle twice is a no-op (idempotence is tested): the harness can be re-dispatched
safely and the cron being late only delays, never corrupts.

Ledger layout (data/ledger/):
- trades.jsonl     append-only, one line per fill
- cycles.jsonl     append-only, one line per processed bar (equities snapshot)
- matchdays.jsonl  append-only, one line per closed matchday (the "jornada")
- state.json       mutable snapshot (portfolios, last processed bar) — its
                   history lives in git; the jsonl files are the record
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from .agents import Agent, Benchmark, Cash, Momentum, MomentumParams, Reversion, ReversionParams
from .bars import build_sessions
from .data import regular_session_only, update_archive
from .engine import Portfolio, step_bar
from .gym import CAPITAL
from .registry import load_all

LEDGER = Path("data/ledger")
UNIVERSE = ("SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA")
NY = ZoneInfo("America/New_York")
BAR_MINUTES = 15
SEASON_1_START = "2026-07-21"  # pre-registered (docs/pre-registration-season-1.md)


def season_of(matchday: str) -> int:
    return 1 if matchday >= SEASON_1_START else 0

# NYSE holidays remaining in 2026 (extend at season roll-over)
HOLIDAYS = {"2026-09-07", "2026-11-26", "2026-12-25"}


def market_day(now_et: datetime) -> bool:
    return now_et.weekday() < 5 and now_et.strftime("%Y-%m-%d") not in HOLIDAYS


def promoted_generation_params(agent: str) -> tuple[str, dict]:
    """The FIELDED generation: last entry in the promotions ledger, never
    merely the latest trained (training alone must not change who plays)."""
    from .promote import current_lineup_ids

    ids = current_lineup_ids()
    if agent not in ids:
        raise RuntimeError(f"no promoted generation for {agent} — seed promotions.jsonl")
    registry = {e["generation_id"]: e for e in load_all()}
    entry = registry[ids[agent]]
    return entry["generation_id"], entry["params"]


def lineup() -> tuple[dict[str, Agent], dict[str, str]]:
    """The live squad: the promoted generation of each trader."""
    mom_id, mom_params = promoted_generation_params("momentum")
    rev_id, rev_params = promoted_generation_params("reversao")
    agents: dict[str, Agent] = {
        "benchmark": Benchmark("SPY"),
        "cash": Cash(),
        "momentum": Momentum(MomentumParams(**{
            k: v for k, v in mom_params.items() if k in MomentumParams.__annotations__})),
        "reversao": Reversion(ReversionParams(**{
            k: v for k, v in rev_params.items() if k in ReversionParams.__annotations__})),
    }
    return agents, {"benchmark": "static", "cash": "static",
                    "momentum": mom_id, "reversao": rev_id}


def _load_state() -> dict:
    path = LEDGER / "state.json"
    if path.exists():
        return json.loads(path.read_text("utf-8"))
    return {"portfolios": {}, "last_ts": None, "matchday": None,
            "day_open_equity": {}, "closed": True, "season": 0}


def _save_state(state: dict) -> None:
    LEDGER.mkdir(parents=True, exist_ok=True)
    (LEDGER / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")


def _portfolio_from(d: dict) -> Portfolio:
    return Portfolio(cash=d["cash"], positions=dict(d["positions"]),
                     entry_price=dict(d["entry_price"]), peak_price=dict(d["peak_price"]),
                     costs_paid=d["costs_paid"])


def _portfolio_to(pf: Portfolio) -> dict:
    return {"cash": pf.cash, "positions": pf.positions, "entry_price": pf.entry_price,
            "peak_price": pf.peak_price, "costs_paid": pf.costs_paid}


def _append(name: str, record: dict) -> None:
    LEDGER.mkdir(parents=True, exist_ok=True)
    with (LEDGER / name).open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_cycle(now: datetime | None = None, fetch: bool = True) -> dict:
    """One arena cycle. Returns a summary for the Actions log."""
    now = now or datetime.now(UTC)
    now_et = now.astimezone(NY)
    if not market_day(now_et):
        return {"status": "closed", "reason": "market holiday/weekend"}

    if fetch:
        for symbol in UNIVERSE:
            update_archive(symbol, "15m", "5d")
    from .data import load_archive

    frames = {s: regular_session_only(load_archive(s, "15m")) for s in UNIVERSE}
    today = now_et.strftime("%Y-%m-%d")
    sessions = [s for s in build_sessions(frames, min_bars=1) if s.date == today]
    if not sessions:
        return {"status": "no-bars", "reason": f"no completed bars for {today} yet"}
    session = sessions[0]

    # completed bars only: a bar stamped T covers T..T+15min
    cutoff = now - timedelta(minutes=BAR_MINUTES)
    complete = [t for t in range(session.n_bars) if session.ts[t] <= cutoff]
    if not complete:
        return {"status": "no-bars", "reason": "first bar still forming"}

    agents, generation_of = lineup()
    state = _load_state()

    if state["matchday"] != today:
        state["matchday"] = today
        state["closed"] = False
        if season_of(today) != state.get("season"):
            # season kickoff: every portfolio resets to the pre-registered capital
            state["season"] = season_of(today)
            state["portfolios"] = {}
            state["last_ts"] = None
        for name in agents:
            if name not in state["portfolios"]:
                state["portfolios"][name] = _portfolio_to(Portfolio(cash=CAPITAL))
        # day-open equity uses the first completed bar's prices
        p0 = {s: float(session.close[s][complete[0]]) for s in session.symbols}
        state["day_open_equity"] = {
            name: _portfolio_from(d).equity(p0) for name, d in state["portfolios"].items()
        }

    portfolios = {name: _portfolio_from(d) for name, d in state["portfolios"].items()}
    last_ts = pd.Timestamp(state["last_ts"]) if state["last_ts"] else None
    session_close_et = now_et.replace(hour=15, minute=45, second=0, microsecond=0)
    processed, new_trades = 0, 0

    for t in complete:
        ts = session.ts[t]
        if last_ts is not None and ts <= last_ts:
            continue
        is_last = ts.tz_convert(NY) >= session_close_et
        step = step_bar(session, t, agents, portfolios, is_last=is_last, debug_checks=True)
        prices = {s: float(session.close[s][t]) for s in session.symbols}
        _append("cycles.jsonl", {
            "season": state["season"], "matchday": today, "ts": ts.isoformat(),
            "equity": {name: eq for name, (eq, _) in step.items()},
            "prices": prices,
        })
        for name, (_, trades) in step.items():
            for trade in trades:
                _append("trades.jsonl", {
                    "season": state["season"], "generation": generation_of[name],
                    "ts": ts.isoformat(), **asdict(trade),
                })
                new_trades += 1
        last_ts = ts
        processed += 1
        if is_last and not state["closed"]:
            final_prices = prices
            results = {name: pf.equity(final_prices) for name, pf in portfolios.items()}
            day_pnl = {name: results[name] - state["day_open_equity"].get(name, CAPITAL)
                       for name in results}
            _append("matchdays.jsonl", {
                "season": state["season"], "matchday": today,
                "generation": generation_of,
                "final_equity": results, "day_pnl": day_pnl,
                "winner": max(day_pnl, key=day_pnl.get),
                "bars": t + 1,
            })
            state["closed"] = True
            break

    state["portfolios"] = {name: _portfolio_to(pf) for name, pf in portfolios.items()}
    state["last_ts"] = last_ts.isoformat() if last_ts is not None else None
    _save_state(state)
    return {"status": "ok", "matchday": today, "bars_processed": processed,
            "trades": new_trades, "closed": state["closed"],
            "equity": {n: round(pf.equity({s: float(session.close[s][complete[-1]])
                                           for s in session.symbols}), 2)
                       for n, pf in portfolios.items()}}


if __name__ == "__main__":
    print(json.dumps(run_cycle(), indent=2, default=str))
