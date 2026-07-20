"""Sessions and the point-in-time MarketView.

No-lookahead is enforced STRUCTURALLY: a MarketView is constructed with sliced
COPIES of the data up to bar t — the object never holds future bars, so no
agent, however creative, can peek (ADR-002). Covered by tests/test_no_lookahead.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Session:
    """One trading day: aligned bars for the whole universe."""

    date: str  # YYYY-MM-DD (America/New_York)
    symbols: tuple[str, ...]
    ts: pd.DatetimeIndex  # bar timestamps, UTC
    open: dict[str, np.ndarray]
    high: dict[str, np.ndarray]
    low: dict[str, np.ndarray]
    close: dict[str, np.ndarray]
    volume: dict[str, np.ndarray]

    @property
    def n_bars(self) -> int:
        return len(self.ts)


class MarketView:
    """What an agent is allowed to see at bar t: history up to and including t."""

    def __init__(self, session: Session, t: int):
        self.t = t
        self.date = session.date
        self.symbols = session.symbols
        end = t + 1
        self._close = {s: session.close[s][:end].copy() for s in session.symbols}
        self._high = {s: session.high[s][:end].copy() for s in session.symbols}
        self._low = {s: session.low[s][:end].copy() for s in session.symbols}
        self._volume = {s: session.volume[s][:end].copy() for s in session.symbols}

    def closes(self, symbol: str) -> np.ndarray:
        return self._close[symbol]

    def highs(self, symbol: str) -> np.ndarray:
        return self._high[symbol]

    def lows(self, symbol: str) -> np.ndarray:
        return self._low[symbol]

    def volumes(self, symbol: str) -> np.ndarray:
        return self._volume[symbol]

    def price(self, symbol: str) -> float:
        return float(self._close[symbol][-1])

    def vwap(self, symbol: str) -> float:
        v = self._volume[symbol]
        total = v.sum()
        if total <= 0:
            return self.price(symbol)
        return float((self._close[symbol] * v).sum() / total)


def build_sessions(frames: dict[str, pd.DataFrame], min_bars: int = 10) -> list[Session]:
    """Align per-symbol bar frames into daily sessions (inner join on timestamps)."""
    symbols = tuple(sorted(frames))
    common = None
    for frame in frames.values():
        idx = frame.index
        common = idx if common is None else common.intersection(idx)
    sessions: list[Session] = []
    dates = common.tz_convert("America/New_York").date
    for date in sorted(set(dates)):
        mask = dates == date
        ts = common[mask]
        if len(ts) < min_bars:
            continue
        sessions.append(
            Session(
                date=str(date),
                symbols=symbols,
                ts=ts,
                open={s: frames[s].loc[ts, "open"].to_numpy(float) for s in symbols},
                high={s: frames[s].loc[ts, "high"].to_numpy(float) for s in symbols},
                low={s: frames[s].loc[ts, "low"].to_numpy(float) for s in symbols},
                close={s: frames[s].loc[ts, "close"].to_numpy(float) for s in symbols},
                volume={s: frames[s].loc[ts, "volume"].to_numpy(float) for s in symbols},
            )
        )
    return sessions
