from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_sentiment_engine
from app.sentiment import SentimentResult


class StubSentimentEngine:
    def __init__(self, result: SentimentResult) -> None:
        self.result = result

    def analyze(self, text: str) -> SentimentResult:
        return self.result


@pytest.fixture()
def client() -> TestClient:
    app.dependency_overrides.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_messages_positive_success(client: TestClient) -> None:
    app.dependency_overrides[get_sentiment_engine] = lambda: StubSentimentEngine(
        SentimentResult(label="POSITIVE", score=0.98, latency_ms=4.21)
    )

    response = client.post("/messages", json={"message": "Great work everyone!"})

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Great work everyone!"
    assert body["sentiment"] == "POSITIVE"
    assert body["score"] == pytest.approx(0.98)
    assert body["latency_ms"] == pytest.approx(4.21)
    timestamp = datetime.fromisoformat(body["timestamp"])
    assert timestamp.tzinfo is not None


def test_messages_negative_success(client: TestClient) -> None:
    app.dependency_overrides[get_sentiment_engine] = lambda: StubSentimentEngine(
        SentimentResult(label="NEGATIVE", score=0.97, latency_ms=3.11)
    )

    response = client.post("/messages", json={"message": "This is extremely frustrating."})

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "This is extremely frustrating."
    assert body["sentiment"] == "NEGATIVE"
    assert 0.0 <= body["score"] <= 1.0
    assert body["latency_ms"] >= 0


def test_messages_validation_and_timestamp(client: TestClient) -> None:
    app.dependency_overrides[get_sentiment_engine] = lambda: StubSentimentEngine(
        SentimentResult(label="POSITIVE", score=0.5, latency_ms=1.0)
    )

    response = client.post("/messages", json={"message": "Great work everyone!"})

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Great work everyone!"
    timestamp = datetime.fromisoformat(body["timestamp"])
    assert timestamp.tzinfo is not None


def test_messages_accepts_maximum_length_message(client: TestClient) -> None:
    app.dependency_overrides[get_sentiment_engine] = lambda: StubSentimentEngine(
        SentimentResult(label="POSITIVE", score=0.5, latency_ms=1.0)
    )
    message = "x" * 1000

    response = client.post("/messages", json={"message": message})

    assert response.status_code == 200
    assert response.json()["message"] == message


@pytest.mark.parametrize(
    "payload,status_code",
    [
        ({}, 422),
        ({"message": None}, 422),
        ({"message": ""}, 422),
        ({"message": "   "}, 400),
        ({"message": "x" * 1001}, 422),
    ],
)
def test_messages_reject_invalid_input(client: TestClient, payload: dict[str, Any], status_code: int) -> None:
    app.dependency_overrides[get_sentiment_engine] = lambda: StubSentimentEngine(
        SentimentResult(label="POSITIVE", score=0.5, latency_ms=1.0)
    )

    response = client.post("/messages", json=payload)

    assert response.status_code == status_code


def test_health_endpoint_still_passes(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
