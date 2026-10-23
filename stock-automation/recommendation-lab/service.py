"""Single-process, bounded request coordinator for the unconnected lab."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time
from uuid import UUID

from core import DataBlocked, analyze, timestamp


class SnapshotFileSource:
    """A server-configured research input, never a path or URL from the browser."""
    def __init__(self, path):
        self.path = Path(path)

    def load(self, deadline):
        if time.monotonic() > deadline:
            raise TimeoutError
        if self.path.suffix.lower() != ".json" or not self.path.is_file():
            raise DataBlocked("REGULAR_RESEARCH_JSON_REQUIRED")
        with self.path.open("rb") as stream:
            data = stream.read(2_000_001)
        if len(data) > 2_000_000:
            raise DataBlocked("INPUT_TOO_LARGE")
        result = json.loads(data, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
        if time.monotonic() > deadline:
            raise TimeoutError
        return result


class RecommendationService:
    def __init__(self, source=None, *, clock=None, monotonic=None, cooldown=15):
        self.source = source
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.monotonic = monotonic or time.monotonic
        self.cooldown = cooldown
        self.lock = threading.Lock()
        self.next_allowed = float("-inf")
        self.results = {}

    def request(self, request_id):
        try:
            valid_id = isinstance(request_id, str) and str(UUID(request_id)) == request_id and UUID(request_id).version == 4
        except ValueError:
            valid_id = False
        if not valid_id:
            return 400, {"status": "BLOCKED", "reason": "INVALID_REQUEST_ID"}
        if not self.lock.acquire(blocking=False):
            return 429, {"status": "BLOCKED", "reason": "ANALYSIS_BUSY"}
        try:
            now = self.clock()
            self.results = {key: value for key, value in self.results.items()
                            if timestamp(value["expires_at"]) > now}
            if request_id in self.results:
                return 200, self.results[request_id]
            if self.source is None:
                return 503, {"status": "BLOCKED", "reason": "DATA_SOURCE_NOT_CONNECTED"}
            tick = self.monotonic()
            if tick < self.next_allowed:
                return 429, {"status": "BLOCKED", "reason": "REQUEST_COOLDOWN",
                             "retry_after_seconds": max(1, int(self.next_allowed - tick) + 1)}
            self.next_allowed = tick + self.cooldown
            deadline = tick + 10
            try:
                snapshot = self.source.load(deadline)
                if self.monotonic() > deadline:
                    raise TimeoutError
                result = analyze(snapshot, now=self.clock())
                if self.monotonic() > deadline:
                    raise TimeoutError
            except TimeoutError:
                return 504, {"status": "TIMEOUT", "reason": "ANALYSIS_DEADLINE"}
            except DataBlocked:
                return 422, {"status": "BLOCKED", "reason": "REQUIRED_DATA_INVALID_OR_STALE"}
            except Exception:
                # Never return raw exceptions, file paths, credentials or provider bodies.
                return 503, {"status": "FAILED", "reason": "DATA_UNAVAILABLE"}
            result["request_id"] = request_id
            if len(self.results) >= 20:
                self.results.pop(next(iter(self.results)))
            self.results[request_id] = result
            return 200, result
        finally:
            self.lock.release()
