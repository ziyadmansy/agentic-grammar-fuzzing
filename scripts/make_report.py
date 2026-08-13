#!/usr/bin/env python3
"""Create a concise Markdown summary from a campaign JSONL artifact."""

import argparse
from collections import Counter
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/report.md"))
    args = parser.parse_args()

    records = [json.loads(line) for line in args.results.read_text().splitlines()]
    statuses = Counter(record["status"] for record in records)
    structures = {record.get("structure", "") for record in records}
    rejections = {record.get("rejection_signature") for record in records if record["status"] == "rejected"}
    crashes = {record.get("crash_id") for record in records if record.get("crash_id")}
    total = len(records)
    accepted = statuses["accepted"]
    acceptance_rate = accepted / total if total else 0.0
    report = "\n".join(
        [
            "# Fuzzing Campaign Report",
            "",
            f"- Inputs executed: {total}",
            f"- Outcomes: {dict(statuses)}",
            f"- Acceptance rate: {acceptance_rate:.1%}",
            f"- Structural fingerprints: {len(structures)}",
            f"- Rejection signatures: {len(rejections)}",
            f"- Sanitizer crash signatures: {len(crashes)}",
            "",
            "Crash counts are reported only when sanitizer stderr is present in the input artifact.",
            "",
        ]
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()