import pytest

from app import sentiment


class DummyClassifier:
    def __init__(self, response: list[dict[str, object]]) -> None:
        self.response = response

    def __call__(self, text: str) -> list[dict[str, object]]:
        return self.response


@pytest.fixture(autouse=True)
def clear_sentiment_cache() -> None:
    sentiment._load_classifier.cache_clear()
    sentiment.get_sentiment_engine.cache_clear()


def test_engine_initialization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sentiment, "_load_classifier", lambda model_id: DummyClassifier([{"label": "POSITIVE", "score": 0.99}]))

    engine = sentiment.get_sentiment_engine("dummy-model")

    assert isinstance(engine, sentiment.SentimentEngine)


def test_positive_classification() -> None:
    engine = sentiment.SentimentEngine(DummyClassifier([{"label": "POSITIVE", "score": 0.98}]))

    result = engine.analyze("I really like this update.")

    assert result.label == "POSITIVE"
    assert result.score == pytest.approx(0.98)
    assert result.latency_ms >= 0


def test_negative_classification() -> None:
    engine = sentiment.SentimentEngine(DummyClassifier([{"label": "NEGATIVE", "score": 0.97}]))

    result = engine.analyze("This is frustrating and broken.")

    assert result.label == "NEGATIVE"
    assert result.score == pytest.approx(0.97)
    assert result.latency_ms >= 0


def test_result_structure_and_score_range() -> None:
    engine = sentiment.SentimentEngine(DummyClassifier([{"label": "NEUTRAL", "score": 0.55}]))

    result = engine.analyze("Maybe we should revisit this later.")

    assert isinstance(result, sentiment.SentimentResult)
    assert isinstance(result.label, str)
    assert isinstance(result.score, float)
    assert 0.0 <= result.score <= 1.0
    assert result.latency_ms >= 0.0


@pytest.mark.parametrize("invalid_text", ["", "   ", None])
def test_empty_or_invalid_input_handling(invalid_text: object) -> None:
    engine = sentiment.SentimentEngine(DummyClassifier([{"label": "POSITIVE", "score": 0.9}]))

    with pytest.raises(ValueError):
        engine.analyze(invalid_text)  # type: ignore[arg-type]
