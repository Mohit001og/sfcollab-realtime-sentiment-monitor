from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable


WINDOW_MINUTES = 60
WINDOW_RULE = "timestamp > now - 60 minutes"


@dataclass(frozen=True, slots=True)
class MoodEntry:
    timestamp: datetime
    signed_score: float


@dataclass(frozen=True, slots=True)
class MoodSnapshot:
    score: float | None
    window_minutes: int
    message_count: int


@dataclass(frozen=True, slots=True)
class MoodHistoryItem:
    timestamp: datetime
    score: float


class RollingMoodService:
    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._entries: list[MoodEntry] = []

    def add_message(self, *, timestamp: datetime, sentiment: str, score: float) -> MoodSnapshot:
        if timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")

        self._entries.append(MoodEntry(timestamp=timestamp, signed_score=_signed_score(sentiment, score)))
        self.prune(now=timestamp)
        return self.snapshot(now=timestamp)

    def prune(self, now: datetime | None = None) -> None:
        current_time = now or self._clock()
        if current_time.tzinfo is None:
            raise ValueError("now must be timezone-aware")

        cutoff = current_time - timedelta(minutes=WINDOW_MINUTES)
        self._entries = [entry for entry in self._entries if entry.timestamp > cutoff]

    def snapshot(self, now: datetime | None = None) -> MoodSnapshot:
        self.prune(now=now)
        if not self._entries:
            return MoodSnapshot(score=None, window_minutes=WINDOW_MINUTES, message_count=0)

        average = sum(entry.signed_score for entry in self._entries) / len(self._entries)
        return MoodSnapshot(score=average, window_minutes=WINDOW_MINUTES, message_count=len(self._entries))

    def entries(self) -> tuple[MoodEntry, ...]:
        return tuple(self._entries)

    def clear(self) -> None:
        self._entries.clear()

    def history(self, now: datetime | None = None) -> tuple[MoodHistoryItem, ...]:
        self.prune(now=now)
        return tuple(
            MoodHistoryItem(timestamp=entry.timestamp, score=entry.signed_score)
            for entry in self._entries
        )


def _signed_score(sentiment: str, score: float) -> float:
    if sentiment == "POSITIVE":
        return score
    if sentiment == "NEGATIVE":
        return -score
    raise ValueError("sentiment must be POSITIVE or NEGATIVE")
