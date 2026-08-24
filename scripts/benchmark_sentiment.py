from pathlib import Path
from time import perf_counter
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.sentiment import SentimentEngine


MESSAGES = [
    "I love this update, great work team!",
    "This is frustrating and disappointing.",
    "Okay.",
    "Can we revisit this after the meeting? I have a few concerns and want to make sure we get this right.",
]


def main() -> None:
    start = perf_counter()
    engine = SentimentEngine.from_model_id()
    load_ms = (perf_counter() - start) * 1000

    timings: list[float] = []
    outputs = []

    for message in MESSAGES:
        message_start = perf_counter()
        result = engine.analyze(message)
        elapsed_ms = (perf_counter() - message_start) * 1000
        timings.append(elapsed_ms)
        outputs.append(
            {
                "message": message,
                "label": result.label,
                "score": result.score,
                "latency_ms": elapsed_ms,
            }
        )

    print({"load_ms": load_ms, "outputs": outputs, "avg_ms": sum(timings) / len(timings), "min_ms": min(timings), "max_ms": max(timings)})


if __name__ == "__main__":
    main()
