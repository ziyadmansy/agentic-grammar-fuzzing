#!/usr/bin/env python3
"""Pre-registered analysis of the parson replication (docs/parson-replication.md).

Reads only each arm's aggregate.json (run scripts/aggregate_runs.py on both arm
directories first) and prints per-run acceptance rates, the exact two-sided
Mann-Whitney U test, and Cliff's delta.

    .venv/bin/python scripts/parson_stats.py \
        artifacts/repeated/parson-baseline-n15 artifacts/repeated/parson-refined-n15
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from scipy.stats import mannwhitneyu


def load(arm_dir: Path) -> tuple[list[dict], list[dict]]:
    runs = json.loads((arm_dir / "aggregate.json").read_text())["per_run"]
    with_data = [r for r in runs if r["executed"] > 0]
    return runs, with_data


def acceptance(run: dict) -> float:
    return 100.0 * run["accepted"] / run["executed"]


def cliffs_delta(a: list[float], b: list[float]) -> float:
    return sum((x > y) - (x < y) for x in a for y in b) / (len(a) * len(b))


def describe(name: str, runs: list[dict], with_data: list[dict]) -> list[float]:
    rates = [acceptance(r) for r in with_data]
    print(f"{name}: {len(with_data)}/{len(runs)} runs with data")
    print(f"  per-run acceptance (%): {[round(x, 2) for x in rates]}")
    print(
        f"  mean {statistics.mean(rates):.2f}, sd {statistics.stdev(rates):.2f}, "
        f"min {min(rates):.2f}, max {max(rates):.2f}"
    )
    print(
        f"  crashes/timeouts/signals: {sum(r['crashes'] for r in runs)}; "
        f"rejected proposals: {sum(r['iterations_rejected'] for r in runs)} of "
        f"{sum(r['iterations'] for r in runs)} iterations; "
        f"inputs executed: {sum(r['executed'] for r in runs)}"
    )
    print(
        f"  fingerprints (sum/run) {statistics.mean(r['structural_fingerprints'] for r in with_data):.1f}; "
        f"rejection signatures (sum/run) {statistics.mean(r['rejection_signatures'] for r in with_data):.1f}"
    )
    return rates


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("baseline", type=Path)
    parser.add_argument("refined", type=Path)
    args = parser.parse_args()

    base = describe("baseline", *load(args.baseline))
    refined = describe("refined", *load(args.refined))
    test = mannwhitneyu(refined, base, alternative="two-sided", method="exact")
    print(
        f"\nrefined - baseline: {statistics.mean(refined) - statistics.mean(base):+.2f} pp, "
        f"exact two-sided Mann-Whitney U={test.statistic:.1f}, p={test.pvalue:.3g}, "
        f"Cliff's delta={cliffs_delta(refined, base):+.2f}"
    )


if __name__ == "__main__":
    main()
