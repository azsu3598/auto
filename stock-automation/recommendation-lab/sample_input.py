"""Create an explicitly fictional, short-lived input for PC-C manual testing only."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

# Reuse fictional test values; this generator is deliberately not in the release archive.
sys.path.insert(0, str(Path(__file__).resolve().parent / "tests"))
from fixtures import snapshot


def sample():
    data = snapshot()
    now = datetime.now(timezone.utc).isoformat()
    for key in ("captured_at", "scanned_at"): data[key] = now
    data["market"]["observed_at"] = now
    for q in data["quotes"]:
        for key in ("observed_at", "flow_at", "technical_at"): q[key] = now
        q["catalyst"]["published_at"] = now; q["catalyst"]["verified_at"] = now
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fictional input only. Never relabel real expired quotes with new timestamps.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(sample(), stream, ensure_ascii=False, indent=2); stream.write("\n")
    print("FICTIONAL_SAMPLE_CREATED: valid for at most 90 seconds; no broker or ledger access")
