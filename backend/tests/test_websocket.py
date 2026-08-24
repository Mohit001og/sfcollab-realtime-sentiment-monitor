from contextlib import ExitStack
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_sentiment_engine, manager, mood_service
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


def test_websocket_connects(client: TestClient) -> None:
    with client.websocket_connect("/ws") as websocket:
        assert websocket is not None
        assert len(manager._active_connections) == 1

    assert len(manager._active_connections) == 0


def test_broadcast_reaches_one_client(client: TestClient) -> None:
    app.dependency_overrides[get_sentiment_engine] = lambda: StubSentimentEngine(
        SentimentResult(label="POSITIVE", score=0.98, latency_ms=4.21)
    )

    with client.websocket_connect("/ws") as websocket:
        response = client.post("/messages", json={"message": "Great work everyone!"})
        payload = websocket.receive_json()

    assert response.status_code == 200
    assert payload["type"] == "message"
    assert payload["data"]["message"] == "Great work everyone!"
    assert payload["data"]["sentiment"] == "POSITIVE"
    assert 0.0 <= payload["data"]["score"] <= 1.0
    assert payload["data"]["latency_ms"] >= 0
    assert payload["mood"]["window_minutes"] == 60
    assert payload["mood"]["score"] == pytest.approx(payload["data"]["score"])
    timestamp = datetime.fromisoformat(payload["data"]["timestamp"])
    assert timestamp.tzinfo is not None


def test_broadcast_reaches_multiple_clients(client: TestClient) -> None:
    app.dependency_overrides[get_sentiment_engine] = lambda: StubSentimentEngine(
        SentimentResult(label="NEGATIVE", score=0.97, latency_ms=3.11)
    )

    with ExitStack() as stack:
        websocket_a = stack.enter_context(client.websocket_connect("/ws"))
        websocket_b = stack.enter_context(client.websocket_connect("/ws"))

        response = client.post("/messages", json={"message": "This is extremely frustrating."})
        payload_a = websocket_a.receive_json()
        payload_b = websocket_b.receive_json()

    assert response.status_code == 200
    assert payload_a == payload_b
    assert payload_a["type"] == "message"
    assert payload_a["data"]["message"] == "This is extremely frustrating."
    assert payload_a["data"]["sentiment"] == "NEGATIVE"


def test_disconnected_client_is_removed_cleanly(client: TestClient) -> None:
    with client.websocket_connect("/ws"):
        assert len(manager._active_connections) == 1

    assert len(manager._active_connections) == 0


def test_post_messages_succeeds_with_no_websocket_clients(client: TestClient) -> None:
    app.dependency_overrides[get_sentiment_engine] = lambda: StubSentimentEngine(
        SentimentResult(label="POSITIVE", score=0.91, latency_ms=2.5)
    )

    response = client.post("/messages", json={"message": "Great work everyone!"})

    assert response.status_code == 200
    assert response.json()["message"] == "Great work everyone!"
    assert mood_service.snapshot().score == pytest.approx(0.91)


def test_invalid_messages_are_not_broadcast(client: TestClient) -> None:
    app.dependency_overrides[get_sentiment_engine] = lambda: StubSentimentEngine(
        SentimentResult(label="POSITIVE", score=0.91, latency_ms=2.5)
    )

    with client.websocket_connect("/ws") as websocket:
        response = client.post("/messages", json={"message": "   "})
        assert response.status_code == 400
        assert len(manager._active_connections) == 1
        assert websocket is not None
        assert mood_service.snapshot().score is None
