"""Create an isolated, review-only archive; never upload or deploy it."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
FILES = ("core.py", "service.py", "server.py", "web/index.html", "web/app.js", "web/styles.css")


def package(output):
    output = Path(output)
    payloads = {name: (ROOT / name).read_bytes() for name in FILES}
    manifest = {"purpose": "RESEARCH_ONLY", "deployment_ready": False,
                "validation_status": "PC_C_TESTS_REQUIRED", "broker_connection": False,
                "files": {name: hashlib.sha256(data).hexdigest() for name, data in payloads.items()}}
    payloads["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    # Mode x preserves any earlier artifact, even if names collide.
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(payloads.items()):
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Review archive only; not deployment approval")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package(args.output)
    print("REVIEW_ARCHIVE_CREATED: not deployed; tests and integration verification required")
