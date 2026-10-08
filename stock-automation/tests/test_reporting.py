from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from stock_automation.engine import ClosingBetEngine
from stock_automation.reporting import append_training_event, write_markdown_report
from test_engine import quote, snapshot


class ReportingTests(unittest.TestCase):
    def test_writes_report_and_compatible_event_row(self):
        snap = snapshot(quote())
        decision = ClosingBetEngine().evaluate(snap, cash=600_000)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = write_markdown_report(root / "reports", snap, decision)
            events = root / "events.csv"
            append_training_event(events, snap, decision)
            self.assertIn("AI 모의매수", report.read_text(encoding="utf-8"))
            with events.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(1, len(rows))
            self.assertEqual("AI_SIMULATED", rows[0]["actual_trade_status"])
            self.assertEqual("BUY", rows[0]["decision"])

    def test_report_does_not_overwrite_same_minute(self):
        snap = snapshot(quote())
        decision = ClosingBetEngine().evaluate(snap, cash=600_000)
        with tempfile.TemporaryDirectory() as directory:
            first = write_markdown_report(directory, snap, decision)
            second = write_markdown_report(directory, snap, decision)
            self.assertNotEqual(first, second)
            self.assertTrue(second.name.endswith("-02.md"))


if __name__ == "__main__":
    unittest.main()
