#!/usr/bin/env python3
"""Compare a grammar-seeded baseline experiment against an LLM-refined one.

Consumes each arm's `aggregate.json` when it exists, and otherwise recomputes
the same numbers from `summary.json`/`manifest.json` with aggregate_runs.py's
own helpers, so the comparison can never disagree with the aggregate tables.
`results.jsonl` is not read and no fuzzing code is imported.

Reported values are means per run. No hypothesis test is performed and no
significance is claimed: the tables are descriptive only.
"""

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aggregate_runs import collect_run, find_run_dirs, summarize  # noqa: E402


# `executed` is not one of the compared outcome metrics, but the arms may run
# different example budgets (a baseline has one iteration, a refined run has
# several), so absolute counts are only interpretable alongside it.
_ROWS = (
    ("executed", "Inputs executed (mean per run)", 1),
    ("accepted", "Accepted (mean per run)", 1),
    ("rejected", "Rejected (mean per run)", 1),
    ("encoding_errors", "Encoding errors (mean per run)", 1),
    ("crashes", "Crashes (mean per run)", 1),
    ("structural_fingerprints", "Structural fingerprints (mean per run)", 1),
    ("rejection_signatures", "Rejection signatures (mean per run)", 1),
    ("acceptance_percentage", "Acceptance rate (%)", 2),
)


def load_arm(root: Path) -> dict[str, Any]:
    """Per-run rows plus per-metric statistics for one experiment directory."""
    run_dirs = find_run_dirs(root)
    if not run_dirs:
        return {"root": root, "runs": 0, "rows": [], "statistics": {}, "problems": [f"no runs found under {root}"]}

    aggregate_path = root / "aggregate.json"
    rows: list[dict[str, Any]] | None = None
    statistics_by_metric: dict[str, Any] | None = None
    problems: list[str] = []
    if aggregate_path.exists():
        try:
            aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
            rows = list(aggregate["per_run"])
            statistics_by_metric = dict(aggregate["statistics"])
        except (ValueError, OSError, KeyError, TypeError) as error:
            problems.append(f"aggregate.json unusable, recomputed from summaries: {error}")
            rows = None
    if rows is None:
        rows = [collect_run(run_dir) for run_dir in run_dirs]
        statistics_by_metric = summarize(rows)

    usable = [row for row in rows if row.get("executed")]
    problems.extend(
        f"{row.get('run')}: {'; '.join(row.get('problems', []))}" for row in rows if row.get("problems")
    )
    executed = [float(row["executed"]) for row in usable]
    statistics_by_metric = dict(statistics_by_metric or {})
    statistics_by_metric["executed"] = {
        "runs": len(executed),
        "mean": sum(executed) / len(executed) if executed else None,
    }
    return {
        "root": root,
        "runs": len(usable),
        "runs_found": len(rows),
        "rows": rows,
        "statistics": statistics_by_metric,
        "problems": problems,
    }


def _mean(arm: dict[str, Any], metric: str) -> float | None:
    value = arm["statistics"].get(metric, {}).get("mean")
    return None if value is None else float(value)


def build_table(baseline: dict[str, Any], refined: dict[str, Any]) -> list[dict[str, Any]]:
    table = []
    for metric, label, digits in _ROWS:
        base = _mean(baseline, metric)
        refine = _mean(refined, metric)
        absolute = None if base is None or refine is None else refine - base
        # a relative change against a zero or absent baseline is undefined
        percentage = None if absolute is None or not base else 100.0 * absolute / base
        table.append(
            {
                "metric": metric,
                "label": label,
                "digits": digits,
                "baseline": base,
                "refined": refine,
                "absolute_difference": absolute,
                "percentage_difference": percentage,
            }
        )
    return table


def _format(value: float | None, digits: int, sign: bool = False) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.{digits}f}" if sign else f"{value:.{digits}f}"


def write_csv(path: Path, table: list[dict[str, Any]], baseline: dict[str, Any], refined: dict[str, Any]) -> None:
    columns = (
        "metric",
        "baseline_mean",
        "refined_mean",
        "absolute_difference",
        "percentage_difference",
        "baseline_runs",
        "refined_runs",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in table:
            writer.writerow(
                {
                    "metric": row["metric"],
                    "baseline_mean": row["baseline"],
                    "refined_mean": row["refined"],
                    "absolute_difference": row["absolute_difference"],
                    "percentage_difference": row["percentage_difference"],
                    "baseline_runs": baseline["runs"],
                    "refined_runs": refined["runs"],
                }
            )


def write_markdown(
    path: Path,
    table: list[dict[str, Any]],
    baseline: dict[str, Any],
    refined: dict[str, Any],
    baseline_label: str,
    refined_label: str,
) -> None:
    lines = [
        "# Baseline versus refined experiments",
        "",
        f"| Metric | {baseline_label} (n = {baseline['runs']}) | {refined_label} (n = {refined['runs']}) "
        "| Absolute difference | Relative difference |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in table:
        unit = " pp" if row["metric"] == "acceptance_percentage" else ""
        lines.append(
            f"| {row['label']} | {_format(row['baseline'], row['digits'])} "
            f"| {_format(row['refined'], row['digits'])} "
            f"| {_format(row['absolute_difference'], row['digits'], sign=True)}{unit} "
            f"| {_format(row['percentage_difference'], 1, sign=True)}{'' if row['percentage_difference'] is None else '%'} |"
        )
    lines += [
        "",
        "Values are means over the runs of each arm; differences are refined minus "
        "baseline. Relative differences are omitted where the baseline mean is zero. "
        "These are descriptive statistics only -- no hypothesis test was performed and "
        "no significance is claimed.",
        "",
        "Structural fingerprint and rejection signature counts are summed over each "
        "run's iterations, so they are upper bounds on a run's distinct shapes; the "
        "two arms may also execute different numbers of inputs per run, which the "
        "first row makes explicit.",
        "",
        f"- {baseline_label}: `{baseline['root']}`",
        f"- {refined_label}: `{refined['root']}`",
    ]
    incomplete = [(baseline_label, baseline), (refined_label, refined)]
    notes = [f"- {label}: {problem}" for label, arm in incomplete for problem in arm["problems"]]
    if notes:
        lines += ["", "Incomplete or missing data:", *notes]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("baseline", type=Path, help="baseline experiment directory")
    parser.add_argument("refined", type=Path, help="refined experiment directory")
    parser.add_argument("--output-dir", type=Path, default=None, help="defaults to the refined directory")
    parser.add_argument("--baseline-label", default="Baseline")
    parser.add_argument("--refined-label", default="Refined")
    args = parser.parse_args()

    baseline = load_arm(args.baseline)
    refined = load_arm(args.refined)
    table = build_table(baseline, refined)

    output_dir = args.output_dir or args.refined
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "comparison.csv"
    markdown_path = output_dir / "comparison.md"
    write_csv(csv_path, table, baseline, refined)
    write_markdown(markdown_path, table, baseline, refined, args.baseline_label, args.refined_label)

    print(f"{args.baseline_label}: {baseline['runs']} run(s) with data")
    print(f"{args.refined_label}: {refined['runs']} run(s) with data")
    for label, arm in ((args.baseline_label, baseline), (args.refined_label, refined)):
        for problem in arm["problems"]:
            print(f"  note: {label}: {problem}")
    print(csv_path)
    print(markdown_path)


if __name__ == "__main__":
    main()
