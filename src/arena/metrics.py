"""Season statistics: bootstrap confidence intervals over daily P&L differences
vs the benchmark — the pre-registered criterion 2 (docs/pre-registration-
season-1.md), implemented once, used by the mid-season report, the season
write-up and the go/no-go evaluation.

Honesty note printed with every report: with few matchdays the intervals are
wide by design — that is the interval doing its job, not a bug.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np

from .live import LEDGER

BOOTSTRAP_RESAMPLES = 10_000  # pre-registered
CONFIDENCE = 0.95
MIN_MATCHDAYS = 40  # pre-registered criterion 4
MAX_DRAWDOWN_FLOOR = -0.10  # pre-registered criterion 3


def daily_diffs(matchdays: list[dict], agent: str, benchmark: str = "benchmark") -> np.ndarray:
    """Per-matchday P&L difference agent-minus-benchmark, in EUR."""
    return np.array([
        m["day_pnl"][agent] - m["day_pnl"][benchmark]
        for m in matchdays
        if agent in m["day_pnl"] and benchmark in m["day_pnl"]
    ])


def bootstrap_ci(
    diffs: np.ndarray,
    n_resamples: int = BOOTSTRAP_RESAMPLES,
    confidence: float = CONFIDENCE,
    seed: int = 42,
) -> tuple[float, float, float]:
    """(lower, mean, upper) of the mean daily difference."""
    if len(diffs) == 0:
        return (float("nan"),) * 3
    rng = np.random.default_rng(seed)
    samples = rng.choice(diffs, size=(n_resamples, len(diffs)), replace=True).mean(axis=1)
    alpha = (1.0 - confidence) / 2.0
    return (
        float(np.quantile(samples, alpha)),
        float(diffs.mean()),
        float(np.quantile(samples, 1.0 - alpha)),
    )


@dataclass(frozen=True)
class AgentSeasonStats:
    agent: str
    matchdays: int
    season_pnl: float
    benchmark_pnl: float
    ci_lower: float
    ci_mean: float
    ci_upper: float
    beats_benchmark_significantly: bool  # criterion 2: CI lower bound > 0


def season_stats(season: int = 1) -> list[AgentSeasonStats]:
    path = LEDGER / "matchdays.jsonl"
    matchdays = [
        json.loads(x) for x in path.read_text("utf-8").splitlines() if x.strip()
    ] if path.exists() else []
    matchdays = [m for m in matchdays if m["season"] == season]
    if not matchdays:
        return []
    agents = sorted(matchdays[0]["day_pnl"])
    out = []
    bench_total = sum(m["day_pnl"]["benchmark"] for m in matchdays)
    for agent in agents:
        diffs = daily_diffs(matchdays, agent)
        lo, mean, hi = bootstrap_ci(diffs)
        out.append(AgentSeasonStats(
            agent=agent,
            matchdays=len(diffs),
            season_pnl=sum(m["day_pnl"][agent] for m in matchdays),
            benchmark_pnl=bench_total,
            ci_lower=lo, ci_mean=mean, ci_upper=hi,
            beats_benchmark_significantly=bool(len(diffs) and lo > 0),
        ))
    return out


def main() -> None:
    stats = season_stats(season=1)
    if not stats:
        print("Época 1 ainda sem jornadas fechadas — nada para calcular.")
        return
    n = stats[0].matchdays
    print(f"Época 1 · {n} jornadas · IC {CONFIDENCE:.0%} bootstrap "
          f"({BOOTSTRAP_RESAMPLES} reamostragens) da diferença diária vs benchmark\n")
    for s in stats:
        verdict = "IC exclui zero ✓" if s.beats_benchmark_significantly else "IC inclui zero"
        print(f"  {s.agent:10s} pnl época {s.season_pnl:>+9.0f} €  "
              f"IC [{s.ci_lower:>+7.0f}, {s.ci_upper:>+7.0f}] €/dia  {verdict}")
    if n < MIN_MATCHDAYS:
        print(f"\nNota: {n} < {MIN_MATCHDAYS} jornadas mínimas do pré-registo — intervalos"
              " largos são o intervalo a fazer o seu trabalho, não um defeito.")


if __name__ == "__main__":
    main()
