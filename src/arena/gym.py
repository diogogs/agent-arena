"""The Gym: walk-forward training over historical sessions (ADR-002).

Optuna searches agent parameters on the TRAIN window only; the best candidate
is then scored once on the VALIDATION window the search never touched. Every
generation reports both — the train/validation gap is a public metric, and the
live Arena later adds the third number.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import optuna

from .agents import (
    TRADABLE,
    Agent,
    Benchmark,
    Momentum,
    MomentumParams,
    Reversion,
    ReversionParams,
)
from .bars import Session
from .engine import Portfolio, run_session

CAPITAL = 100_000.0


@dataclass
class Metrics:
    final_equity: float
    pnl: float
    max_drawdown: float
    trades: int
    costs_paid: float
    vs_benchmark: float  # pnl minus benchmark pnl over the same sessions


def evaluate(agent: Agent, sessions: list[Session], benchmark_symbol: str = "SPY") -> Metrics:
    agents = {"x": agent, "bench": Benchmark(benchmark_symbol)}
    portfolios = {name: Portfolio(cash=CAPITAL) for name in agents}
    curve: list[float] = []
    trades = 0
    for session in sessions:
        day = run_session(session, agents, portfolios)
        curve.extend(day["x"].equity_curve)
        trades += len(day["x"].trades)
    eq = np.array(curve)
    peak = np.maximum.accumulate(eq)
    last_prices = {s: float(sessions[-1].close[s][-1]) for s in sessions[-1].symbols}
    bench_pnl = portfolios["bench"].equity(last_prices) - CAPITAL
    final = float(eq[-1])
    return Metrics(
        final_equity=final,
        pnl=final - CAPITAL,
        max_drawdown=float(((eq - peak) / peak).min()),
        trades=trades,
        costs_paid=portfolios["x"].costs_paid,
        vs_benchmark=(final - CAPITAL) - bench_pnl,
    )


def _suggest_momentum(trial: optuna.Trial) -> MomentumParams:
    return MomentumParams(
        or_bars=trial.suggest_int("or_bars", 1, 6),
        breakout=trial.suggest_float("breakout", 0.0002, 0.005, log=True),
        trail=trial.suggest_float("trail", 0.002, 0.02, log=True),
        per_symbol_fraction=trial.suggest_float("per_symbol_fraction", 0.1, 0.34),
    )


def _suggest_reversion(trial: optuna.Trial) -> ReversionParams:
    return ReversionParams(
        z_entry=trial.suggest_float("z_entry", -3.0, -1.0),
        z_exit=trial.suggest_float("z_exit", -0.5, 0.5),
        z_bail=trial.suggest_float("z_bail", -5.0, -3.0),
        sigma_window=trial.suggest_int("sigma_window", 6, 26),
        per_symbol_fraction=trial.suggest_float("per_symbol_fraction", 0.1, 0.34),
    )

def _make(cls, params):
    return cls(params, tradable=TRADABLE)


FACTORIES = {
    "momentum": (lambda p: _make(Momentum, p), _suggest_momentum),
    "reversao": (lambda p: _make(Reversion, p), _suggest_reversion),
}


@dataclass
class Generation:
    agent: str
    params: dict
    train: Metrics
    validation: Metrics
    n_trials: int
    train_sessions: tuple[str, str]  # first, last date
    val_sessions: tuple[str, str]


def train_generation(
    agent_name: str,
    sessions: list[Session],
    val_fraction: float = 0.3,
    n_trials: int = 60,
    seed: int = 42,
) -> Generation:
    """One walk-forward generation: optimize on train, score once on validation."""
    cls, suggest = FACTORIES[agent_name]
    split = int(len(sessions) * (1.0 - val_fraction))
    train, val = sessions[:split], sessions[split:]

    def objective(trial: optuna.Trial) -> float:
        # Amendment 3 (2026-07-20): turnover penalty — costs are double-counted
        # in the training objective so the gym learns to rotate less
        metrics = evaluate(cls(suggest(trial)), train)
        return metrics.vs_benchmark - metrics.costs_paid

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize",
                                sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    best = cls(suggest(optuna.trial.FixedTrial(study.best_params)))
    return Generation(
        agent=agent_name,
        params=study.best_params,
        train=evaluate(best, train),
        validation=evaluate(best, val),
        n_trials=n_trials,
        train_sessions=(train[0].date, train[-1].date),
        val_sessions=(val[0].date, val[-1].date),
    )


def rolling_tournament(
    agent_name: str,
    sessions: list[Session],
    n_windows: int = 6,
    train_len: int = 28,
    val_len: int = 12,
    n_trials: int = 40,
    seed: int = 1000,
) -> list[Generation]:
    """Amendment 1: the strategy's re-trainability across rolling windows.
    The FINAL window's generation is the fielding candidate; the MEDIAN of the
    validation vs_benchmark across windows is its promotion score."""
    generations = []
    step = max(1, (len(sessions) - train_len - val_len) // max(n_windows - 1, 1))
    for k in range(n_windows):
        window = sessions[k * step : k * step + train_len + val_len]
        if len(window) < train_len + val_len:
            break
        generations.append(train_generation(
            agent_name, window, val_fraction=val_len / (train_len + val_len),
            n_trials=n_trials, seed=seed + k,
        ))
    return generations


