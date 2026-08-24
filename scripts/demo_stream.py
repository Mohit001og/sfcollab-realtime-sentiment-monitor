"""Send a local demo stream through the SFCollab backend.

The script posts realistic team-chat messages to POST /messages and reports
the sentiment values returned by the running backend. It does not infer,
mock, or hard-code sentiment results.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
DEFAULT_DELAY_SECONDS = 2.0
REQUEST_TIMEOUT_SECONDS = 10

DEMO_MESSAGES = [
    "Great work everyone, the deployment finished successfully.",
    "The login bug is still blocking testing and it is frustrating.",
    "I finished the API contract review and left notes in the ticket.",
    "The requirements around the dashboard filters are still confusing.",
    "QA found one flaky test, but the rest of the release checks passed.",
    "Thanks for jumping on the production alert so quickly.",
    "The design review is delayed until tomorrow afternoon.",
    "I am worried about the memory usage on the free hosting tier.",
    "The WebSocket updates are flowing smoothly in the dashboard.",
    "I need clarification before I can complete the chart polish.",
    "Nice progress on the sentiment endpoint and the mood summary.",
    "The latest build is failing locally and I cannot reproduce the issue yet.",
]


@dataclass
class StreamStats:
    sent: int = 0
    positive: int = 0
    negative: int = 0
    other: int = 0
    latency_total_ms: float = 0.0
    latency_count: int = 0

    def record(self, response: dict[str, Any]) -> None:
        self.sent += 1
        sentiment = str(response.get("sentiment", "")).upper()
        if sentiment == "POSITIVE":
            self.positive += 1
        elif sentiment == "NEGATIVE":
            self.negative += 1
        else:
            self.other += 1

        latency = response.get("latency_ms")
        if isinstance(latency, int | float):
            self.latency_total_ms += float(latency)
            self.latency_count += 1

    @property
    def average_latency_ms(self) -> float | None:
        if self.latency_count == 0:
            return None
        return self.latency_total_ms / self.latency_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SFCollab Real-Time Sentiment Monitor demo stream",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_BACKEND_URL,
        help=f"Backend base URL. Default: {DEFAULT_BACKEND_URL}",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help=f"Delay between messages in seconds. Default: {DEFAULT_DELAY_SECONDS}",
    )
    return parser.parse_args()


def messages_url(base_url: str) -> str:
    normalized = base_url.rstrip("/") + "/"
    return urljoin(normalized, "messages")


def post_message(endpoint: str, message: str) -> tuple[int, dict[str, Any]]:
    payload = json.dumps({"message": message}).encode("utf-8")
    request = Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        body = response.read().decode("utf-8")
        data = json.loads(body) if body else {}
        return response.status, data


def print_response(index: int, total: int, status: int, response: dict[str, Any]) -> None:
    sentiment = response.get("sentiment", "UNKNOWN")
    score = response.get("score", "n/a")
    latency = response.get("latency_ms", "n/a")
    timestamp = response.get("timestamp", "n/a")

    print(f"[{index}/{total}] HTTP {status}")
    print(f"  message: {response.get('message', '')}")
    print(f"  sentiment: {sentiment} | score: {score} | latency_ms: {latency}")
    print(f"  timestamp: {timestamp}")


def run_stream(endpoint: str, delay: float) -> StreamStats:
    stats = StreamStats()
    total = len(DEMO_MESSAGES)

    print("SFCollab Real-Time Sentiment Monitor demo stream")
    print(f"Endpoint: {endpoint}")
    print(f"Messages: {total}")
    print(f"Delay: {delay:.2f}s")
    print()

    for index, message in enumerate(DEMO_MESSAGES, start=1):
        print(f"Sending: {message}")
        status, response = post_message(endpoint, message)
        stats.record(response)
        print_response(index, total, status, response)
        print()

        if index < total and delay > 0:
            time.sleep(delay)

    return stats


def main() -> int:
    args = parse_args()
    if args.delay < 0:
        print("Error: --delay must be zero or greater.", file=sys.stderr)
        return 2

    endpoint = messages_url(args.url)
    try:
        stats = run_stream(endpoint, args.delay)
    except HTTPError as exc:
        print(f"Backend returned HTTP {exc.code}: {exc.reason}", file=sys.stderr)
        return 1
    except URLError as exc:
        print(f"Could not connect to backend at {args.url}: {exc.reason}", file=sys.stderr)
        return 1
    except TimeoutError:
        print(f"Timed out connecting to backend at {args.url}.", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"Backend returned invalid JSON: {exc}", file=sys.stderr)
        return 1

    average_latency = stats.average_latency_ms
    print("Demo stream complete")
    print(f"Messages sent: {stats.sent}")
    print(f"Positive responses: {stats.positive}")
    print(f"Negative responses: {stats.negative}")
    print(f"Other sentiment labels: {stats.other}")
    if average_latency is None:
        print("Average backend latency: n/a")
    else:
        print(f"Average backend latency: {average_latency:.2f} ms")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
