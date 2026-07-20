"""Weekly retrain + gated promotion (the automated learning loop, ADR-002).

Pre-registration rules (as amended 2026-07-20) enforced in code:
- promotions only on MONDAYS, before the US open; at most one per agent/week;
- Amendment 1: the challenger is the final-window generation of a six-window
  rolling tournament, promoted only if the tournament MEDIAN of validation
  vs_benchmark is positive AND strictly beats the incumbent's score;
- everything lands insert-only: new generations in the registry, promotions in
  data/ledger/promotions.jsonl. The live lineup reads promotions, never
  "latest trained" — training alone never changes who plays.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .bars import build_sessions
from .data import load_archive, regular_session_only
from .registry import load_all, record

PROMOTIONS = Path("data/ledger/promotions.jsonl")
UNIVERSE = ("SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA")
NY = ZoneInfo("America/New_York")


def load_promotions() -> list[dict]:
    if not PROMOTIONS.exists():
        return []
    return [json.loads(x) for x in PROMOTIONS.read_text("utf-8").splitlines() if x.strip()]


def current_lineup_ids() -> dict[str, str]:
    """agent -> generation_id currently fielded (last promotion per agent)."""
    lineup: dict[str, str] = {}
    for p in load_promotions():
        lineup[p["agent"]] = p["generation_id"]
    return lineup


def _append_promotion(entry: dict) -> None:
    PROMOTIONS.parent.mkdir(parents=True, exist_ok=True)
    with PROMOTIONS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def promotion_window_open(now: datetime) -> bool:
    """Mondays before the US open (pre-registration)."""
    now_et = now.astimezone(NY)
    return now_et.weekday() == 0 and (now_et.hour, now_et.minute) < (9, 30)


def incumbent_score(entry: dict | None) -> float | None:
    """Amendment 1: tournament median when the incumbent has one, else its
    single-split validation (the g001 kickoff case)."""
    if entry is None:
        return None
    if "tournament_median" in entry:
        return float(entry["tournament_median"])
    return float(entry["validation"]["vs_benchmark"])


def decide_promotion(challenger_median: float, incumbent: float | None) -> tuple[bool, str]:
    """Amendment 1 gate: the challenger's rolling-tournament MEDIAN must be
    positive AND strictly beat the incumbent's score."""
    if challenger_median <= 0:
        return False, f"tournament median {challenger_median:+.0f} is not positive"
    if incumbent is None:
        return True, f"kickoff lineup (tournament median {challenger_median:+.0f})"
    if challenger_median > incumbent:
        return True, f"tournament median {challenger_median:+.0f} beats incumbent {incumbent:+.0f}"
    return False, f"tournament median {challenger_median:+.0f} does not beat incumbent {incumbent:+.0f}"


def weekly_retrain(now: datetime | None = None, n_trials: int = 40) -> list[dict]:
    """Rolling tournament per agent; the last window's generation is the
    fielding candidate, gated by the tournament MEDIAN (Amendment 1)."""
    import statistics

    from .gym import rolling_tournament

    now = now or datetime.now(UTC)
    frames = {s: regular_session_only(load_archive(s, "15m")) for s in UNIVERSE}
    sessions = build_sessions(frames)
    registry = {e["generation_id"]: e for e in load_all()}
    lineup = current_lineup_ids()
    outcomes = []
    for agent in ("momentum", "reversao"):
        generations = rolling_tournament(agent, sessions, n_trials=n_trials,
                                         seed=2000 + len(sessions))
        if not generations:
            outcomes.append({"agent": agent, "promoted": False,
                             "reason": "not enough sessions for a tournament"})
            continue
        median = statistics.median(g.validation.vs_benchmark for g in generations)
        for g in generations[:-1]:
            record(g, note=f"weekly tournament {now:%Y-%m-%d}")
        entry = record(generations[-1], note=f"weekly tournament {now:%Y-%m-%d} — candidate",
                       extra={"tournament_median": round(median, 2), "candidate": True})
        promote, reason = decide_promotion(median, incumbent_score(registry.get(lineup.get(agent))))
        window = promotion_window_open(now)
        if promote and window:
            _append_promotion({
                "ts": now.isoformat(), "agent": agent,
                "generation_id": entry["generation_id"], "reason": reason,
            })
        outcomes.append({
            "agent": agent, "generation_id": entry["generation_id"],
            "tournament_median": round(median, 2),
            "promoted": bool(promote and window),
            "reason": reason if window else f"outside promotion window — {reason}",
        })
    return outcomes


if __name__ == "__main__":
    for outcome in weekly_retrain():
        print(json.dumps(outcome, ensure_ascii=False))
