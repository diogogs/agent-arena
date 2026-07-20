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


def build_payload() -> dict:
    cycles = _lines("cycles.jsonl")
    trades = _lines("trades.jsonl")
    matchdays = _lines("matchdays.jsonl")
    if not cycles:
        raise RuntimeError("empty ledger — run at least one live cycle first")

    latest_day = cycles[-1]["matchday"]
    day_cycles = [c for c in cycles if c["matchday"] == latest_day]
    day_trades = [t for t in trades if t["session"] == latest_day]
    agents = sorted(day_cycles[0]["equity"])
    closed = any(m["matchday"] == latest_day for m in matchdays)

    # season standings: latest equity per agent + matchdays won
    standings = {a: {"equity": day_cycles[-1]["equity"][a], "won": 0} for a in agents}
    for m in matchdays:
        if m["winner"] in standings:
            standings[m["winner"]]["won"] += 1

    generations: dict[str, str] = {}
    for t in day_trades:
        generations.setdefault(t["agent"], t.get("generation", ""))
    return {
        "matchday": latest_day,
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
        "standings": standings,
        "n_matchdays": len(matchdays),
        "generations": generations,
    }


def build_site() -> Path:
    DOCS.mkdir(exist_ok=True)
    payload = json.dumps(build_payload(), ensure_ascii=False, separators=(",", ":"))
    html = TEMPLATE.read_text("utf-8").replace("__DATA__", payload, 1)
    out = DOCS / "index.html"
    out.write_text(html, encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    return out


if __name__ == "__main__":
    print(f"site: {build_site()}")
