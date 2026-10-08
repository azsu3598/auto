from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol


class LedgerDecision(Protocol):
    idempotency_key: str

    def to_dict(self) -> dict[str, Any]: ...


class DuplicateDecisionError(RuntimeError):
    pass


class JsonlLedger:
    """Append-only local ledger; S3/DynamoDB adapters can implement the same contract."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, decision: LedgerDecision) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing = self.read_all()
        if any(row.get("idempotency_key") == decision.idempotency_key for row in existing):
            raise DuplicateDecisionError(decision.idempotency_key)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(decision.to_dict(), ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
        return rows
