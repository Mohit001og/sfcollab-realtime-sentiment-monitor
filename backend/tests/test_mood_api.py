from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_sentiment_engine, mood_service, manager
from app.sentiment import SentimentResult


class StubSentimentEngine:
    def __init__(self, result: SentimentResult) -> None:
        self.result = result

    def analyze(self, text: str) -> SentimentResult:
        return self.result


@pytest.fixture(autouse=True)
def clear_state() -> None:
    app.dependency_overrides.clear()
    manager._active_connections.clear()
    mood_service.clear()
    yield
    app.dependency_overrides.clear()
    manager._active_connections.clear()
    mood_service.clear()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_empty_mood_state_returns_null_and_empty_history(client: TestClient) -> None:
    response = client.get("/mood")

    assert response.status_code == 200
    body = response.json()
    assert body["score"] is None
    assert body["message_count"] == 0
    assert body["window_minutes"] == 60
    assert body["history"] == []


def test_positive_message_updates_mood_endpoint(client: TestClient) -> None:
    app.dependency_overrides[get_sentiment_engine] = lambda: StubSentimentEngine(
        SentimentResult(label="POSITIVE", score=0.9, latency_ms=1.0)
    )

    post_response = client.post("/messages", json={"message": "Great work everyone!"})
    mood_response = client.get("/mood")

    assert post_response.status_code == 200
    assert mood_response.status_code == 200
    body = mood_response.json()
    assert body["score"] == pytest.approx(0.9)
    assert body["message_count"] == 1
    assert len(body["history"]) == 1
    assert body["history"][0]["score"] == pytest.approx(0.9)


def test_multiple_messages_produce_correct_arithmetic_mean(client: TestClient) -> None:
    app.dependency_overrides[get_sentiment_engine] = lambda: StubSentimentEngine(
        SentimentResult(label="POSITIVE", score=0.8, latency_ms=1.0)
    )
    client.post("/messages", json={"message": "Great work everyone!"})
    app.dependency_overrides[get_sentiment_engine] = lambda: StubSentimentEngine(
        SentimentResult(label="NEGATIVE", score=0.2, latency_ms=1.0)
    )
    client.post("/messages", json={"message": "This is frustrating."})

    response = client.get("/mood")

    assert response.status_code == 200
    body = response.json()
    assert body["score"] == pytest.approx(0.3)
    assert body["message_count"] == 2
    assert [item["score"] for item in body["history"]] == pytest.approx([0.8, -0.2])


def test_expired_entries_are_not_included_by_current_time() -> None:
    from app.mood import RollingMoodService

    fixed_now = datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc)
    service = RollingMoodService(clock=lambda: fixed_now)
    old_timestamp = datetime(2026, 8, 24, 8, 59, tzinfo=timezone.utc)
    service.add_message(timestamp=old_timestamp, sentiment="POSITIVE", score=0.9)

    snapshot = service.snapshot(now=fixed_now)

    assert snapshot.score is None
    assert snapshot.message_count == 0
    assert service.history(now=fixed_now) == ()


def test_history_contains_only_timezone_aware_utc_entries(client: TestClient) -> None:
    app.dependency_overrides[get_sentiment_engine] = lambda: StubSentimentEngine(
        SentimentResult(label="POSITIVE", score=0.75, latency_ms=1.0)
    )

    client.post("/messages", json={"message": "Great work everyone!"})
    body = client.get("/mood").json()

    assert body["history"]
    timestamp = datetime.fromisoformat(body["history"][0]["timestamp"])
    assert timestamp.tzinfo is not None
    assert timestamp.utcoffset() == timezone.utc.utcoffset(timestamp)
