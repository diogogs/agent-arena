"""Static site builder: ledger -> docs/ (GitHub Pages).

The arena page is the approved J1 mockup experience fed by REAL ledger data:
replay of the latest matchday (or the live day in progress), league table,
trade feed with reasons, season standings. No server, no cold start.
"""

from __future__ import annotations

import json
from pathlib import Path

from .live import LEDGER, UNIVERSE

DOCS = Path("docs")
TEMPLATE = Path(__file__).parent / "templates" / "arena.html"

LABELS = {"benchmark": "Benchmark (SPY)", "cash": "Cash", "momentum": "Momentum",
          "reversao": "Reversão (VWAP)"}


def _lines(name: str) -> list[dict]:
    path = LEDGER / name
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text("utf-8").splitlines() if x.strip()]


def day_payload(cycles: list[dict], trades: list[dict], matchdays: list[dict],
                day: str) -> dict:
    day_cycles = [c for c in cycles if c["matchday"] == day]
    if not day_cycles:
        raise ValueError(f"no cycles for matchday {day}")
    day_trades = [t for t in trades if t["session"] == day]
    agents = sorted(day_cycles[0]["equity"])
    closed = any(m["matchday"] == day for m in matchdays)
    generations: dict[str, str] = {}
    for t in day_trades:
        generations.setdefault(t["agent"], t.get("generation", ""))
    return {
        "matchday": day,
        "live": not closed,
        "season": day_cycles[0]["season"],
        "ts": [c["ts"] for c in day_cycles],
        "agents": {a: {"label": LABELS.get(a, a),
                       "equity": [round(c["equity"][a], 2) for c in day_cycles]}
                   for a in agents},
        "trades": [
            {"agent": t["agent"], "symbol": t["symbol"], "side": t["side"],
             "price": round(t["price"], 2), "reason": t["reason"], "ts": t["ts"],
             "generation": t.get("generation", "")}
            for t in day_trades
        ],
        "tickers": {s: [round(c["prices"][s], 2) for c in day_cycles]
                    for s in UNIVERSE if s in day_cycles[0]["prices"]},
        "generations": generations,
    }


def build_payload() -> dict:
    cycles = _lines("cycles.jsonl")
    trades = _lines("trades.jsonl")
    matchdays = _lines("matchdays.jsonl")
    if not cycles:
        raise RuntimeError("empty ledger — run at least one live cycle first")

    latest_day = cycles[-1]["matchday"]
    payload = day_payload(cycles, trades, matchdays, latest_day)
    day_cycles = [c for c in cycles if c["matchday"] == latest_day]
    agents = sorted(day_cycles[0]["equity"])

    # season standings: latest equity per agent + matchdays won (current season)
    season = payload["season"]
    standings = {a: {"equity": day_cycles[-1]["equity"][a], "won": 0} for a in agents}
    for m in matchdays:
        if m["season"] == season and m["winner"] in standings:
            standings[m["winner"]]["won"] += 1

    # matchday calendar (all seasons, newest first)
    days = [{"matchday": m["matchday"], "season": m["season"], "winner": m["winner"]}
            for m in matchdays]
    if not any(d["matchday"] == latest_day for d in days):
        days.append({"matchday": latest_day, "season": season, "winner": None})
    days.sort(key=lambda d: d["matchday"], reverse=True)

    payload.update({
        "standings": standings,
        "n_matchdays": sum(1 for m in matchdays if m["season"] == season),
        "days": days,
    })
    return payload


def build_ginasio_payload() -> dict:
    from .promote import current_lineup_ids, load_promotions
    from .registry import load_all

    return {
        "generations": [
            {"generation_id": e["generation_id"], "agent": e["agent"],
             "train": e["train"], "validation": e["validation"],
             "train_sessions": e["train_sessions"]}
            for e in load_all()
        ],
        "promotions": load_promotions(),
        "lineup": current_lineup_ids(),
    }


def build_site() -> Path:
    DOCS.mkdir(exist_ok=True)
    index_payload = build_payload()
    html = TEMPLATE.read_text("utf-8").replace(
        "__DATA__", json.dumps(index_payload, ensure_ascii=False, separators=(",", ":")), 1
    )
    out = DOCS / "index.html"
    out.write_text(html, encoding="utf-8")

    # one JSON per matchday so the arena can replay any past day
    cycles = _lines("cycles.jsonl")
    trades = _lines("trades.jsonl")
    matchdays = _lines("matchdays.jsonl")
    data_dir = DOCS / "data"
    data_dir.mkdir(exist_ok=True)
    for day in sorted({c["matchday"] for c in cycles}):
        (data_dir / f"{day}.json").write_text(
            json.dumps(day_payload(cycles, trades, matchdays, day),
                       ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

    gym_payload = json.dumps(build_ginasio_payload(), ensure_ascii=False, separators=(",", ":"))
    gym_template = TEMPLATE.parent / "ginasio.html"
    (DOCS / "ginasio.html").write_text(
        gym_template.read_text("utf-8").replace("__DATA__", gym_payload, 1), encoding="utf-8"
    )

    preseason_data = DOCS / "data" / "preseason.json"
    if preseason_data.exists():
        (DOCS / "preepoca.html").write_text(
            (TEMPLATE.parent / "preepoca.html").read_text("utf-8").replace(
                "__DATA__", preseason_data.read_text("utf-8"), 1
            ),
            encoding="utf-8",
        )
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    return out


if __name__ == "__main__":
    print(f"site: {build_site()}")
