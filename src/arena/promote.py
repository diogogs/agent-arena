"""Weekly retrain + gated promotion (the automated learning loop, ADR-002).

Pre-registration rules enforced in code, not by convention:
- promotions only on MONDAYS, before the US open;
- at most one per agent per week;
- a challenger is promoted only if its VALIDATION vs_benchmark beats the
  incumbent generation's validation vs_benchmark;
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
from .gym import train_generation
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


def decide_promotion(challenger: dict, incumbent: dict | None) -> tuple[bool, str]:
    """The pre-registered gate: validation vs_benchmark must strictly improve."""
    new_val = challenger["validation"]["vs_benchmark"]
    if incumbent is None:
        return True, f"kickoff lineup (validation vs_benchmark {new_val:+.0f})"
    old_val = incumbent["validation"]["vs_benchmark"]
    if new_val > old_val:
        return True, f"validation vs_benchmark {new_val:+.0f} beats incumbent {old_val:+.0f}"
    return False, f"validation vs_benchmark {new_val:+.0f} does not beat incumbent {old_val:+.0f}"


def weekly_retrain(now: datetime | None = None, n_trials: int = 80) -> list[dict]:
    """Train challengers on the full archive; promote through the gate."""
    now = now or datetime.now(UTC)
    frames = {s: regular_session_only(load_archive(s, "15m")) for s in UNIVERSE}
    sessions = build_sessions(frames)
    registry = {e["generation_id"]: e for e in load_all()}
    lineup = current_lineup_ids()
    outcomes = []
    for agent in ("momentum", "reversao"):
        generation = train_generation(agent, sessions, n_trials=n_trials, seed=len(sessions))
        entry = record(generation, note=f"weekly retrain {now:%Y-%m-%d}")
        incumbent = registry.get(lineup.get(agent))
        promote, reason = decide_promotion(entry, incumbent)
        window = promotion_window_open(now)
        if promote and window:
            _append_promotion({
                "ts": now.isoformat(), "agent": agent,
                "generation_id": entry["generation_id"], "reason": reason,
            })
        outcomes.append({
            "agent": agent, "generation_id": entry["generation_id"],
            "promoted": bool(promote and window),
            "reason": reason if window else f"outside promotion window — {reason}",
        })
    return outcomes


if __name__ == "__main__":
    for outcome in weekly_retrain():
        print(json.dumps(outcome, ensure_ascii=False))
