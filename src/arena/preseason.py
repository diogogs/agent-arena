"""The super pre-season: friendlies don't count — they teach (author call,
2026-07-20, on the eve of season 1).

Three exercises, all honest by construction:
1. Stability tournament: K generations per agent trained on ROLLING windows of
   the 15m archive, each validated strictly out-of-window — a DISTRIBUTION of
   validation outcomes instead of a single lucky split.
2. The two-year friendly: 1h-bar generations trained on 2023-2025 history and
   the full league replayed across ~2 years of regimes (rate shock, rallies).
   Different bar size from the live season — labeled as an exhibition, counts
   for nothing.
3. Cost stress: the season lineup re-evaluated at 1x/2x/4x frictions.

Output: docs/data/preseason.json (site input) + registry entries (insert-only,
noted as pre-season) for every generation trained here.
"""

from __future__ import annotations

import json
from pathlib import Path

from .agents import Benchmark, Cash, Momentum, MomentumParams, Reversion, ReversionParams
from .bars import build_sessions
from .data import load_archive, regular_session_only
from .engine import Portfolio, cost_scale, run_session
from .gym import CAPITAL, evaluate, train_generation
from .promote import UNIVERSE, current_lineup_ids
from .registry import load_all, record

OUT = Path("docs/data/preseason.json")

TRAIN_LEN, VAL_LEN, N_ORIGINS = 28, 12, 6


def _sessions(interval: str, min_bars: int):
    frames = {s: regular_session_only(load_archive(s, interval)) for s in UNIVERSE}
    return build_sessions(frames, min_bars=min_bars)


def stability_tournament(n_trials: int = 40) -> dict:
    sessions = _sessions("15m", 10)
    step = max(1, (len(sessions) - TRAIN_LEN - VAL_LEN) // (N_ORIGINS - 1))
    results: dict[str, list] = {}
    for agent in ("momentum", "reversao"):
        rows = []
        for k in range(N_ORIGINS):
            start = k * step
            window = sessions[start : start + TRAIN_LEN + VAL_LEN]
            if len(window) < TRAIN_LEN + VAL_LEN:
                break
            generation = train_generation(
                agent, window, val_fraction=VAL_LEN / (TRAIN_LEN + VAL_LEN),
                n_trials=n_trials, seed=1000 + k,
            )
            record(generation, note=f"pre-season stability tournament, origin {k}")
            rows.append({
                "origin": k,
                "train_span": generation.train_sessions,
                "val_span": generation.val_sessions,
                "train_vs_bench": round(generation.train.vs_benchmark),
                "val_vs_bench": round(generation.validation.vs_benchmark),
                "val_trades": generation.validation.trades,
            })
        results[agent] = rows
    return results


def two_year_friendly(n_trials: int = 60) -> dict:
    sessions = _sessions("1h", 5)
    gens = {}
    for agent in ("momentum", "reversao"):
        generation = train_generation(agent, sessions, n_trials=n_trials, seed=77)
        record(generation, note="pre-season two-year friendly (1h bars)")
        gens[agent] = generation

    agents = {
        "benchmark": Benchmark("SPY"),
        "cash": Cash(),
        "momentum": Momentum(MomentumParams(**{
            k: v for k, v in gens["momentum"].params.items()
            if k in MomentumParams.__annotations__})),
        "reversao": Reversion(ReversionParams(**{
            k: v for k, v in gens["reversao"].params.items()
            if k in ReversionParams.__annotations__})),
    }
    portfolios = {name: Portfolio(cash=CAPITAL) for name in agents}
    curve = {name: [] for name in agents}
    dates = []
    for session in sessions:
        day = run_session(session, agents, portfolios)
        dates.append(session.date)
        for name in agents:
            curve[name].append(round(day[name].equity_curve[-1]))
    return {
        "dates": dates,
        "equity": curve,
        "generations": {a: {"params": g.params,
                            "train_vs_bench": round(g.train.vs_benchmark),
                            "val_vs_bench": round(g.validation.vs_benchmark)}
                        for a, g in gens.items()},
    }


def cost_stress() -> list[dict]:
    sessions = _sessions("15m", 10)
    registry = {e["generation_id"]: e for e in load_all()}
    lineup = current_lineup_ids()
    cls = {"momentum": (Momentum, MomentumParams), "reversao": (Reversion, ReversionParams)}
    rows = []
    for agent, (agent_cls, params_cls) in cls.items():
        params = registry[lineup[agent]]["params"]
        instance = lambda: agent_cls(params_cls(**{  # noqa: E731
            k: v for k, v in params.items() if k in params_cls.__annotations__}))
        for scale in (1.0, 2.0, 4.0):
            with cost_scale(scale):
                metrics = evaluate(instance(), sessions)
            rows.append({
                "agent": agent, "generation": lineup[agent], "cost_scale": scale,
                "pnl": round(metrics.pnl), "vs_bench": round(metrics.vs_benchmark),
                "costs_paid": round(metrics.costs_paid), "trades": metrics.trades,
            })
    return rows


def main() -> None:
    print("1/3 torneio de estabilidade (12 gerações em janelas rolantes)…")
    tournament = stability_tournament()
    print("2/3 a grande amigável de 2 anos (1h)…")
    friendly = two_year_friendly()
    print("3/3 stress de custos…")
    stress = cost_stress()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "tournament": tournament, "friendly": friendly, "stress": stress,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"pré-época escrita em {OUT}")
    for agent, rows in tournament.items():
        vals = [r["val_vs_bench"] for r in rows]
        print(f"  {agent:10s} validação vs bench nas {len(vals)} janelas: "
              f"min {min(vals):+d}  max {max(vals):+d}")
    for row in stress:
        if row["cost_scale"] == 4.0:
            print(f"  {row['agent']:10s} a 4x custos: pnl {row['pnl']:+d} "
                  f"(custos pagos {row['costs_paid']})")


if __name__ == "__main__":
    main()
