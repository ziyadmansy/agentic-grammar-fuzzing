#!/usr/bin/env python3
"""Aggregate completed experiment runs into paper-ready statistics.

Reads only each run's per-iteration `summary.json` (and `manifest.json` when
present); `results.jsonl` is never re-parsed, since every required field is
already recorded. This script knows nothing about the fuzzing pipeline beyond
those two artifact formats, and writes nothing back into them.

Point it either at a directory of `run-*` directories or at a single run
directory containing `iteration-*`.
"""

import argparse
import csv
import json
from pathlib import Path
import statistics
from typing import Any

# Statuses accounted for by name; every other status key in `counts` (crash,
# timeout, signal:*) is a failure, matching scripts/make_loop_report.py.
_NAMED_STATUSES = {"accepted", "rejected", "encoding_error", "proposal_rejected"}

_METRICS = (
    "accepted",
    "rejected",
    "encoding_errors",
    "crashes",
    "structural_fingerprints",
    "rejection_signatures",
    "acceptance_percentage",
)

_COLUMNS = (
    "run",
    "seed",
    "model",
    "timestamp",
    "iterations",
    "iterations_with_data",
    "iterations_rejected",
    "executed",
    *_METRICS,
    "problems",
)


def find_run_dirs(root: Path) -> list[Path]:
    runs = sorted(path for path in root.glob("run-*") if path.is_dir())
    if runs:
        return runs
    if any(root.glob("iteration-*")):
        return [root]
    return []


def _iteration_dirs(run_dir: Path) -> list[Path]:
    return sorted(
        (path for path in run_dir.glob("iteration-*") if path.is_dir()),
        key=lambda path: int(path.name.split("-")[1]),
    )


def _read_manifest(run_dir: Path) -> tuple[dict[str, Any], list[str]]:
    path = run_dir / "manifest.json"
    if not path.exists():
        return {}, ["manifest.json missing"]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except (ValueError, OSError) as error:
        return {}, [f"manifest.json unreadable: {error}"]


def collect_run(run_dir: Path) -> dict[str, Any]:
    """Fold one run's iteration summaries into a single row, never raising."""
    manifest, problems = _read_manifest(run_dir)
    totals = dict.fromkeys(("accepted", "rejected", "encoding_errors", "crashes"), 0)
    totals.update(structural_fingerprints=0, rejection_signatures=0, executed=0)
    iteration_dirs = _iteration_dirs(run_dir)
    if not iteration_dirs:
        problems.append("no iteration directories")
    with_data = 0
    rejected_iterations = 0

    for iteration_dir in iteration_dirs:
        summary_path = iteration_dir / "summary.json"
        if not summary_path.exists():
            problems.append(f"{iteration_dir.name}/summary.json missing")
            continue
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            counts = dict(summary["counts"])
            total = int(summary["total"])
            structures = int(summary["unique_structures"])
            rejections = int(summary["unique_rejections"])
        except (ValueError, OSError, KeyError, TypeError) as error:
            problems.append(f"{iteration_dir.name}/summary.json unusable: {error}")
            continue

        if "proposal_rejected" in counts:
            # the proposal never ran, so it contributes no campaign observations
            rejected_iterations += 1
            continue

        with_data += 1
        totals["accepted"] += int(counts.get("accepted", 0))
        totals["rejected"] += int(counts.get("rejected", 0))
        totals["encoding_errors"] += int(counts.get("encoding_error", 0))
        totals["crashes"] += sum(
            int(value) for key, value in counts.items() if key not in _NAMED_STATUSES
        )
        # per-iteration uniques are summed: cross-iteration de-duplication is not
        # recoverable from summary.json, so this is an upper bound on the run's
        # distinct shapes, on the same per-iteration basis as make_loop_report.py.
        totals["structural_fingerprints"] += structures
        totals["rejection_signatures"] += rejections
        totals["executed"] += total

    executed = totals["executed"]
    return {
        "run": run_dir.name,
        "seed": manifest.get("seed"),
        "model": manifest.get("model"),
        "timestamp": manifest.get("timestamp"),
        "iterations": len(iteration_dirs),
        "iterations_with_data": with_data,
        "iterations_rejected": rejected_iterations,
        **totals,
        "acceptance_percentage": round(100.0 * totals["accepted"] / executed, 3) if executed else None,
        "problems": problems,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Mean/sd/min/max per metric over the runs that produced observations."""
    usable = [row for row in rows if row["executed"] > 0]
    statistics_by_metric: dict[str, Any] = {}
    for metric in _METRICS:
        values = [float(row[metric]) for row in usable if row[metric] is not None]
        statistics_by_metric[metric] = {
            "runs": len(values),
            "mean": round(statistics.mean(values), 3) if values else None,
            # sample standard deviation; undefined for a single run
            "stdev": round(statistics.stdev(values), 3) if len(values) > 1 else None,
            "min": min(values) if values else None,
            "max": max(values) if values else None,
        }
    return statistics_by_metric


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", type=Path, help="directory of run-* dirs, or one run directory")
    parser.add_argument("--output-dir", type=Path, default=None, help="defaults to ROOT")
    args = parser.parse_args()

    run_dirs = find_run_dirs(args.root)
    if not run_dirs:
        raise SystemExit(f"no runs found under {args.root}")

    rows = [collect_run(run_dir) for run_dir in run_dirs]
    usable = [row for row in rows if row["executed"] > 0]
    incomplete = [
        {"run": row["run"], "problems": row["problems"]} for row in rows if row["problems"]
    ]

    output_dir = args.output_dir or args.root
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "aggregate.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "problems": "; ".join(row["problems"])})

    json_path = output_dir / "aggregate.json"
    json_path.write_text(
        json.dumps(
            {
                "source": str(args.root),
                "runs_found": len(rows),
                "runs_with_data": len(usable),
                "incomplete_runs": incomplete,
                "per_run": rows,
                "statistics": summarize(rows),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"{len(usable)}/{len(rows)} runs with data")
    for entry in incomplete:
        print(f"  incomplete: {entry['run']}: {'; '.join(entry['problems'])}")
    print(csv_path)
    print(json_path)


if __name__ == "__main__":
    main()
