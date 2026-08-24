from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from time import perf_counter
from typing import Callable, Protocol


DEFAULT_MODEL_ID = "takedarn/bert-tiny-sst2"


class _Classifier(Protocol):
    def __call__(self, text: str) -> list[dict[str, object]]: ...


@dataclass(frozen=True, slots=True)
class SentimentResult:
    label: str
    score: float
    latency_ms: float


class SentimentEngine:
    def __init__(self, classifier: _Classifier) -> None:
        self._classifier = classifier

    @classmethod
    def from_model_id(cls, model_id: str = DEFAULT_MODEL_ID) -> "SentimentEngine":
        classifier = _load_classifier(model_id)
        return cls(classifier)

    def analyze(self, text: str) -> SentimentResult:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string")

        started = perf_counter()
        prediction = self._classifier(text)[0]
        latency_ms = (perf_counter() - started) * 1000

        label = str(prediction["label"])
        score = float(prediction["score"])
        return SentimentResult(label=_normalize_label(label), score=score, latency_ms=latency_ms)


@lru_cache(maxsize=1)
def get_sentiment_engine(model_id: str = DEFAULT_MODEL_ID) -> SentimentEngine:
    return SentimentEngine.from_model_id(model_id)


@lru_cache(maxsize=1)
def _load_classifier(model_id: str) -> _Classifier:
    from transformers import pipeline

    return pipeline("text-classification", model=model_id, truncation=True)


def _normalize_label(label: str) -> str:
    if label == "LABEL_0":
        return "NEGATIVE"
    if label == "LABEL_1":
        return "POSITIVE"
    return label.upper()
