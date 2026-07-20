"""The promotion gate (Amendment 1: rolling-tournament median), enforced in code."""

from datetime import UTC, datetime

from arena.promote import decide_promotion, incumbent_score, promotion_window_open


def test_challenger_median_must_be_positive_and_beat_incumbent():
    ok, _ = decide_promotion(500.0, 200.0)
    assert ok
    ok, reason = decide_promotion(200.0, 500.0)
    assert not ok and "does not beat" in reason
    ok, _ = decide_promotion(500.0, 500.0)
    assert not ok  # ties do not promote
    ok, reason = decide_promotion(-50.0, -900.0)
    assert not ok and "not positive" in reason  # beating a bad incumbent is not enough


def test_kickoff_without_incumbent_still_requires_positive_median():
    ok, reason = decide_promotion(300.0, None)
    assert ok and "kickoff" in reason
    ok, _ = decide_promotion(-100.0, None)
    assert not ok


def test_incumbent_score_prefers_tournament_median():
    assert incumbent_score({"tournament_median": 42.0,
                            "validation": {"vs_benchmark": 999.0}}) == 42.0
    assert incumbent_score({"validation": {"vs_benchmark": 123.0}}) == 123.0
    assert incumbent_score(None) is None


def test_promotion_window_is_monday_before_open():
    monday_early = datetime(2026, 7, 27, 11, 45, tzinfo=UTC)  # 07:45 ET, Monday
    assert promotion_window_open(monday_early)
    monday_open = datetime(2026, 7, 27, 14, 0, tzinfo=UTC)  # 10:00 ET — market open
    assert not promotion_window_open(monday_open)
    tuesday = datetime(2026, 7, 28, 11, 45, tzinfo=UTC)
    assert not promotion_window_open(tuesday)
