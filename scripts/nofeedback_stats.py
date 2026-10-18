#!/usr/bin/env python3
"""Pre-registered analysis of the no-feedback control (docs/no-feedback-control.md).

Reads each arm's aggregate.json (run scripts/aggregate_runs.py on every arm
directory first) and prints per-run acceptance, the primary test (refined with
feedback against no feedback) and the descriptive secondary measures.

    .venv/bin/python scripts/nofeedback_stats.py \
        artifacts/repeated/cjson-baseline-n15 artifacts/repeated/cjson-baseline-validonly-n15 \
        artifacts/repeated/cjson-refined-n15 artifacts/repeated/cjson-nofeedback-n15
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from scipy.stats import mannwhitneyu


def load(arm_dir: Path) -> tuple[list[dict], list[dict]]:
    runs = json.loads((arm_dir / "aggregate.json").read_text())["per_run"]
    return runs, [r for r in runs if r["executed"] > 0]


def acceptance(run: dict) -> float:
    return 100.0 * run["accepted"] / run["executed"]


def cliffs_delta(a: list[float], b: list[float]) -> float:
    return sum((x > y) - (x < y) for x in a for y in b) / (len(a) * len(b))


def describe(name: str, runs: list[dict], with_data: list[dict]) -> list[float]:
    rates = [acceptance(r) for r in with_data]
    executed = sum(r["executed"] for r in with_data)
    iterations = sum(r["iterations_with_data"] for r in with_data)
    print(f"{name}: {len(with_data)}/{len(runs)} runs with data")
    print(f"  per-run acceptance (%): {[round(x, 2) for x in rates]}")
    print(
        f"  mean {statistics.mean(rates):.2f}, sd {statistics.stdev(rates):.2f}, "
        f"min {min(rates):.2f}, max {max(rates):.2f}"
    )
    print(
        f"  inputs executed {executed}; rejected {100.0 * sum(r['rejected'] for r in with_data) / executed:.2f}%; "
        f"runs with no rejected input {sum(r['rejected'] == 0 for r in with_data)}"
    )
    print(
        f"  fingerprints per 500-input iteration "
        f"{sum(r['structural_fingerprints'] for r in with_data) / iterations:.1f}; "
        f"rejected proposals {sum(r['iterations_rejected'] for r in runs)} of {sum(r['iterations'] for r in runs)}; "
        f"crashes/timeouts/signals {sum(r['crashes'] for r in runs)}"
    )
    return rates


def compare(label: str, a: list[float], b: list[float]) -> None:
    test = mannwhitneyu(a, b, alternative="two-sided", method="exact")
    print(
        f"{label}: {statistics.mean(a) - statistics.mean(b):+.2f} pp, exact two-sided "
        f"Mann-Whitney U={test.statistic:.1f}, p={test.pvalue:.3g}, Cliff's delta={cliffs_delta(a, b):+.2f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("baseline", type=Path)
    parser.add_argument("valid_only", type=Path)
    parser.add_argument("refined", type=Path)
    parser.add_argument("no_feedback", type=Path)
    args = parser.parse_args()

    base = describe("static baseline", *load(args.baseline))
    describe("valid-half baseline", *load(args.valid_only))
    refined = describe("refined (feedback full)", *load(args.refined))
    blind = describe("no feedback", *load(args.no_feedback))
    print()
    compare("PRIMARY refined - no feedback", refined, blind)
    compare("secondary no feedback - static baseline", blind, base)


if __name__ == "__main__":
    main()
