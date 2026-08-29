from fastapi.testclient import TestClient

from app import main


def test_startup_preloads_sentiment_engine(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_get_sentiment_engine():
        calls["count"] += 1
        return object()

    monkeypatch.setattr(main, "get_sentiment_engine", fake_get_sentiment_engine)

    with TestClient(main.app):
        pass

    assert calls["count"] == 1


client = TestClient(main.app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
