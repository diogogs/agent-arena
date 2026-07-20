"""Intraday bars: fetch (yfinance, keyless) + an insert-only local archive.

Reality of free sources (verified in J2): yfinance serves ~60 days of 15-minute
bars and ~730 days of hourly bars, no key required. The archive strategy makes
that enough: every fetch MERGES new bars into a per-symbol parquet archive and
never deletes, so our own 15m history grows past the source's window as long as
the ingest runs regularly. Alpaca/Polygon (author account pending) can later
backfill deeper history into the same archives.

Bars are stored tz-aware UTC, one row per (symbol, ts): open/high/low/close/volume.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ARCHIVE = Path("data/archive")

COLUMNS = ["open", "high", "low", "close", "volume"]


def _archive_path(symbol: str, interval: str) -> Path:
    return ARCHIVE / interval / f"{symbol}.parquet"


def fetch_yf(symbol: str, interval: str, period: str) -> pd.DataFrame:
    """One yfinance call, normalized to (ts UTC index, ohlcv)."""
    import yfinance as yf

    raw = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=False)
    if raw.empty:
        return pd.DataFrame(columns=COLUMNS)
    frame = raw.rename(columns=str.lower)[COLUMNS]
    frame.index = pd.DatetimeIndex(frame.index).tz_convert("UTC")
    frame.index.name = "ts"
    return frame


def update_archive(symbol: str, interval: str = "15m", period: str = "60d") -> pd.DataFrame:
    """Fetch and merge into the insert-only archive; returns the full archive.

    Existing rows are never modified or deleted: on overlap the ALREADY-ARCHIVED
    row wins (history is immutable once recorded).
    """
    path = _archive_path(symbol, interval)
    fresh = fetch_yf(symbol, interval, period)
    if path.exists():
        old = pd.read_parquet(path)
        old.index = pd.DatetimeIndex(old.index)
        merged = pd.concat([old, fresh[~fresh.index.isin(old.index)]]).sort_index()
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        merged = fresh
    merged.to_parquet(path)
    return merged


def load_archive(symbol: str, interval: str = "15m") -> pd.DataFrame:
    path = _archive_path(symbol, interval)
    if not path.exists():
        raise FileNotFoundError(f"no archive for {symbol} @ {interval}; run update_archive first")
    frame = pd.read_parquet(path)
    frame.index = pd.DatetimeIndex(frame.index)
    return frame


def regular_session_only(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep 09:30-16:00 America/New_York bars (drops pre/after-market rows)."""
    local = frame.index.tz_convert("America/New_York")
    minutes = local.hour * 60 + local.minute
    return frame[(minutes >= 570) & (minutes < 960)]
