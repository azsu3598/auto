from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class KiwoomRetryPolicy:
    """Conservative pacing for Kiwoom's read APIs.

    The broker does not publish one universal requests-per-second value for all
    TR groups. The adapter therefore spaces calls and retries only explicit
    rate-limit, HTTP 429/5xx, and transport failures. Business/input errors are
    never retried.
    """

    min_interval_seconds: float = 0.25
    max_attempts: int = 4
    initial_backoff_seconds: float = 0.75
    maximum_backoff_seconds: float = 6.0

    def __post_init__(self) -> None:
        if self.min_interval_seconds < 0:
            raise ValueError("min_interval_seconds must be non-negative")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if self.initial_backoff_seconds < 0 or self.maximum_backoff_seconds < 0:
            raise ValueError("backoff values must be non-negative")


class ReliableKiwoomClient:
    """Rate-paced, bounded-retry facade around the official helper client."""

    def __init__(
        self,
        client: Any,
        policy: KiwoomRetryPolicy | None = None,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client
        self.policy = policy or KiwoomRetryPolicy()
        self._monotonic = monotonic
        self._sleep = sleep
        self._last_request_started: float | None = None

    def fetch_page(self, **kwargs):
        if kwargs.get("path") == "/api/dostk/ordr":
            raise RuntimeError(
                "ReliableKiwoomClient is read-only; order requests must use the non-retrying live broker"
            )
        delay = self.policy.initial_backoff_seconds
        for attempt in range(1, self.policy.max_attempts + 1):
            self._pace()
            try:
                return self.client.fetch_page(**kwargs)
            except Exception as exc:
                if attempt >= self.policy.max_attempts or not _is_transient(exc):
                    raise
                if delay:
                    self._sleep(delay)
                delay = min(
                    self.policy.maximum_backoff_seconds,
                    max(delay * 2.0, self.policy.initial_backoff_seconds),
                )
        raise AssertionError("retry loop terminated unexpectedly")

    def _pace(self) -> None:
        now = self._monotonic()
        if self._last_request_started is not None:
            remaining = self.policy.min_interval_seconds - (now - self._last_request_started)
            if remaining > 0:
                self._sleep(remaining)
                now = self._monotonic()
        self._last_request_started = now


def _is_transient(exc: Exception) -> bool:
    if getattr(exc, "return_code", None) in {1700, 1701, 1702}:
        return True
    status = getattr(exc, "status_code", None)
    if status == 429 or (isinstance(status, int) and 500 <= status <= 599):
        return True
    return type(exc).__name__ in {
        "Timeout",
        "ConnectTimeout",
        "ReadTimeout",
        "ConnectionError",
    }
