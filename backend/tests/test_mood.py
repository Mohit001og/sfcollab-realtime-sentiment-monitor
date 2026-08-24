from datetime import datetime, timedelta, timezone

import pytest

from app.mood import MoodSnapshot, RollingMoodService, WINDOW_MINUTES, WINDOW_RULE


def make_utc(minutes_offset: int = 0) -> datetime:
    return datetime(2026, 8, 24, 8, 0, tzinfo=timezone.utc) + timedelta(minutes=minutes_offset)


def test_positive_message_maps_to_positive_signed_score() -> None:
    service = RollingMoodService(clock=lambda: make_utc())

    snapshot = service.add_message(timestamp=make_utc(), sentiment="POSITIVE", score=0.9)

    assert isinstance(snapshot, MoodSnapshot)
    assert snapshot.score == pytest.approx(0.9)
    assert snapshot.message_count == 1


def test_negative_message_maps_to_negative_signed_score() -> None:
    service = RollingMoodService(clock=lambda: make_utc())

    snapshot = service.add_message(timestamp=make_utc(), sentiment="NEGATIVE", score=0.8)

    assert snapshot.score == pytest.approx(-0.8)
    assert snapshot.message_count == 1


def test_signed_value_conversion_and_mean_for_multiple_messages() -> None:
    service = RollingMoodService(clock=lambda: make_utc())
    service.add_message(timestamp=make_utc(), sentiment="POSITIVE", score=0.8)
    service.add_message(timestamp=make_utc(1), sentiment="NEGATIVE", score=0.2)
    snapshot = service.snapshot(now=make_utc(1))

    assert snapshot.score == pytest.approx(0.3)
    assert snapshot.message_count == 2


def test_expired_entries_are_removed_outside_sixty_minutes() -> None:
    service = RollingMoodService(clock=lambda: make_utc(61))
    service.add_message(timestamp=make_utc(), sentiment="POSITIVE", score=0.9)
    snapshot = service.snapshot(now=make_utc(61))

    assert snapshot.score is None
    assert snapshot.message_count == 0


def test_entries_inside_sixty_minutes_are_retained() -> None:
    service = RollingMoodService(clock=lambda: make_utc(59))
    service.add_message(timestamp=make_utc(), sentiment="POSITIVE", score=0.9)
    snapshot = service.snapshot(now=make_utc(59))

    assert snapshot.score == pytest.approx(0.9)
    assert snapshot.message_count == 1


def test_exact_sixty_minute_boundary_is_excluded() -> None:
    service = RollingMoodService(clock=lambda: make_utc(60))
    service.add_message(timestamp=make_utc(), sentiment="POSITIVE", score=0.9)
    snapshot = service.snapshot(now=make_utc(60))

    assert snapshot.score is None
    assert snapshot.message_count == 0


def test_empty_window_returns_none() -> None:
    service = RollingMoodService(clock=lambda: make_utc())

    snapshot = service.snapshot(now=make_utc())

    assert snapshot.score is None
    assert snapshot.message_count == 0


def test_timezone_aware_timestamps_required() -> None:
    service = RollingMoodService(clock=lambda: make_utc())

    with pytest.raises(ValueError):
        service.add_message(timestamp=datetime(2026, 8, 24, 8, 0), sentiment="POSITIVE", score=0.9)


def test_deterministic_clock_supports_testing_without_waiting() -> None:
    clock_time = make_utc()
    service = RollingMoodService(clock=lambda: clock_time)

    service.add_message(timestamp=clock_time, sentiment="POSITIVE", score=0.7)
    snapshot = service.snapshot()

    assert snapshot.score == pytest.approx(0.7)
    assert WINDOW_MINUTES == 60
    assert WINDOW_RULE == "timestamp > now - 60 minutes"
