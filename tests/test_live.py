"""Live cycle: idempotence, incremental processing, matchday close."""

import json
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

import arena.data as data
import arena.live as live
from arena.agents import Benchmark, Cash, Momentum, Reversion


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "ARCHIVE", tmp_path / "archive")
    monkeypatch.setattr(live, "LEDGER", tmp_path / "ledger")
    monkeypatch.setattr(live, "UNIVERSE", ("SPY",))
    monkeypatch.setattr(
        live, "lineup",
        lambda: ({"benchmark": Benchmark("SPY"), "cash": Cash(),
                  "momentum": Momentum(), "reversao": Reversion()},
                 {"benchmark": "static", "cash": "static",
                  "momentum": "momentum-t01", "reversao": "reversao-t01"}),
    )
    # synthetic full session for Monday 2026-07-13 (26 x 15m bars, 09:30-15:45 ET)
    rng = np.random.default_rng(1)
    ts = pd.date_range("2026-07-13 13:30", periods=26, freq="15min", tz="UTC")
    closes = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.001, 26)))
    frame = pd.DataFrame(
        {"open": closes, "high": closes * 1.001, "low": closes * 0.999,
         "close": closes, "volume": np.full(26, 1e6)}, index=ts)
    frame.index.name = "ts"
    path = tmp_path / "archive" / "15m" / "SPY.parquet"
    path.parent.mkdir(parents=True)
    frame.to_parquet(path)
    return tmp_path


def _lines(tmp_path, name):
    path = tmp_path / "ledger" / name
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text("utf-8").splitlines() if x.strip()]


def test_full_day_then_idempotent(sandbox):
    after_close = datetime(2026, 7, 13, 21, 0, tzinfo=UTC)
    first = live.run_cycle(now=after_close, fetch=False)
    assert first["status"] == "ok" and first["closed"]
    assert first["bars_processed"] == 26
    assert len(_lines(sandbox, "cycles.jsonl")) == 26
    assert len(_lines(sandbox, "matchdays.jsonl")) == 1

    again = live.run_cycle(now=after_close, fetch=False)
    assert again["bars_processed"] == 0 and again["trades"] == 0
    assert len(_lines(sandbox, "cycles.jsonl")) == 26  # nothing appended
    assert len(_lines(sandbox, "matchdays.jsonl")) == 1


def test_incremental_cycles_close_once(sandbox):
    midday = datetime(2026, 7, 13, 17, 0, tzinfo=UTC)  # 13:00 ET
    partial = live.run_cycle(now=midday, fetch=False)
    assert partial["status"] == "ok" and not partial["closed"]
    n_partial = partial["bars_processed"]
    assert 0 < n_partial < 26

    after_close = datetime(2026, 7, 13, 21, 0, tzinfo=UTC)
    rest = live.run_cycle(now=after_close, fetch=False)
    assert rest["closed"]
    assert n_partial + rest["bars_processed"] == 26
    matchday = _lines(sandbox, "matchdays.jsonl")
    assert len(matchday) == 1
    # intraday agents end the day flat; the record carries every agent
    assert set(matchday[0]["final_equity"]) == {"benchmark", "cash", "momentum", "reversao"}


def test_weekend_is_a_noop(sandbox):
    saturday = datetime(2026, 7, 18, 15, 0, tzinfo=UTC)
    assert live.run_cycle(now=saturday, fetch=False)["status"] == "closed"
