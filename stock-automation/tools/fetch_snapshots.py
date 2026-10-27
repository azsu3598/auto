"""Download saved closing-bet snapshots from the paper S3 bucket, read-only.

Only GetObject on the three fixed snapshot keys of each requested date is used.
No upload, delete, listing, DynamoDB, ECS, order or secret calls. Files are
written outside the repository and never overwrite an existing file.
Feed the output folder to tools/rejection_report.py.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SESSION = "KRX_1520"
SNAPSHOT_PHASES = ("scan_1450", "shortlist_1510", "entry_1520")


def snapshot_keys(day: date, session: str = SESSION) -> list[str]:
    return [f"runs/{day:%Y/%m/%d}/{session}/{phase}-snapshot.json" for phase in SNAPSHOT_PHASES]


def _inside_repository(path: Path) -> bool:
    try:
        path.resolve().relative_to(REPO_ROOT)
    except ValueError:
        return False
    return True


def fetch(s3, bucket: str, days: list[date], out_dir: Path) -> list[dict]:
    """Download snapshots with an S3-like client exposing only get_object."""
    if _inside_repository(out_dir):
        raise ValueError("output folder must be outside the repository")
    results: list[dict] = []
    for day in days:
        for key in snapshot_keys(day):
            target = out_dir / f"{day:%Y%m%d}" / Path(key).name
            row = {"key": key, "file": str(target), "status": "", "detail": ""}
            results.append(row)
            if target.exists():
                row.update(status="SKIPPED_EXISTS", detail="existing file was not overwritten")
                continue
            try:
                body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
            except Exception as exc:  # report every failure verbatim, never retry or widen access
                code = getattr(exc, "response", {}).get("Error", {}).get("Code", type(exc).__name__)
                status = "NOT_FOUND" if code in {"NoSuchKey", "404", "NotFound"} else "ERROR"
                row.update(status=status, detail=f"{code}: {exc}")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            row.update(status="DOWNLOADED", detail=f"{len(body)} bytes")
    return results


def _parse_day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"date must be YYYY-MM-DD: {value}") from exc


def main(argv: list[str] | None = None, s3_factory=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket", default=os.getenv("PAPER_BUCKET"), help="paper bucket (default: PAPER_BUCKET)")
    parser.add_argument("--region", default=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"))
    parser.add_argument("--date", dest="days", action="append", required=True, type=_parse_day,
                        help="trading date YYYY-MM-DD (repeatable)")
    parser.add_argument("--out", required=True, type=Path, help="folder outside the repository")
    args = parser.parse_args(argv)
    if not args.bucket:
        parser.error("give --bucket or set PAPER_BUCKET")
    if _inside_repository(args.out):
        parser.error("--out must be outside the repository (snapshots are raw market data)")
    if s3_factory is None:
        import boto3

        def s3_factory():
            return boto3.client("s3", region_name=args.region) if args.region else boto3.client("s3")

    results = fetch(s3_factory(), args.bucket, args.days, args.out)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for row in results:
        print(f"{row['status']:<15} {row['key']}  {row['detail']}")
    downloaded = sum(1 for row in results if row["status"] == "DOWNLOADED")
    print(f"\n내려받음 {downloaded}/{len(results)}개 -> {args.out}")
    return 0 if downloaded else 1


if __name__ == "__main__":
    raise SystemExit(main())
