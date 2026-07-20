"""The pre-registered promotion gate, enforced in code."""

from datetime import UTC, datetime

from arena.promote import decide_promotion, promotion_window_open


def _gen(val_vs_bench: float) -> dict:
    return {"validation": {"vs_benchmark": val_vs_bench}}


def test_challenger_must_strictly_beat_incumbent_validation():
    ok, _ = decide_promotion(_gen(500.0), _gen(200.0))
    assert ok
    ok, reason = decide_promotion(_gen(200.0), _gen(500.0))
    assert not ok and "does not beat" in reason
    ok, _ = decide_promotion(_gen(500.0), _gen(500.0))
    assert not ok  # ties do not promote


def test_kickoff_without_incumbent_promotes():
    ok, reason = decide_promotion(_gen(-100.0), None)
    assert ok and "kickoff" in reason


def test_promotion_window_is_monday_before_open():
    monday_early = datetime(2026, 7, 27, 11, 45, tzinfo=UTC)  # 07:45 ET, Monday
    assert promotion_window_open(monday_early)
    monday_open = datetime(2026, 7, 27, 14, 0, tzinfo=UTC)  # 10:00 ET — market open
    assert not promotion_window_open(monday_open)
    tuesday = datetime(2026, 7, 28, 11, 45, tzinfo=UTC)
    assert not promotion_window_open(tuesday)
