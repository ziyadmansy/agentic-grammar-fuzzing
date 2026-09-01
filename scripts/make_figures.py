#!/usr/bin/env python3
"""Render publication figures from existing experiment summaries.

Reads only `iteration-N/summary.json` and, when present, `aggregate.json`;
`results.jsonl` is never opened. This script imports no fuzzing code -- it
shares only the run/iteration discovery helpers from aggregate_runs.py so the
two reports cannot drift apart.

Figures are styled for direct inclusion in a paper and encode series by marker
and line style rather than colour, so they survive grayscale printing.
"""

import argparse
import json
from pathlib import Path
import statistics
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aggregate_runs import collect_run, find_run_dirs, iteration_dirs  # noqa: E402


FIGURE_SIZE = (5.5, 3.4)
_GRAYS = ("0.0", "0.35", "0.55", "0.25", "0.45")
_MARKERS = ("o", "s", "^", "D", "v")
_LINESTYLES = ("-", "--", "-.", ":", (0, (3, 1, 1, 1)))

_STYLE = {
    "figure.figsize": FIGURE_SIZE,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "legend.fontsize": 8,
    "legend.frameon": False,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "axes.grid": True,
    "grid.linewidth": 0.4,
    "grid.alpha": 0.4,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "lines.linewidth": 1.2,
    "lines.markersize": 4,
}


def _series_style(index: int) -> dict[str, Any]:
    return {
        "color": _GRAYS[index % len(_GRAYS)],
        "marker": _MARKERS[index % len(_MARKERS)],
        "linestyle": _LINESTYLES[index % len(_LINESTYLES)],
    }


def read_iterations(run_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Per-iteration metrics for one run; a gap is left where data is missing."""
    points: list[dict[str, Any]] = []
    problems: list[str] = []
    for iteration_dir in iteration_dirs(run_dir):
        number = int(iteration_dir.name.split("-")[1])
        summary_path = iteration_dir / "summary.json"
        if not summary_path.exists():
            problems.append(f"{run_dir.name}/{iteration_dir.name}: summary.json missing")
            continue
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            counts = dict(summary["counts"])
            total = int(summary["total"])
        except (ValueError, OSError, KeyError, TypeError) as error:
            problems.append(f"{run_dir.name}/{iteration_dir.name}: summary.json unusable: {error}")
            continue
        if "proposal_rejected" in counts or total == 0:
            # the proposal never ran; plot a break rather than a misleading zero
            problems.append(f"{run_dir.name}/{iteration_dir.name}: no campaign data (proposal rejected)")
            continue
        points.append(
            {
                "iteration": number,
                "acceptance_percentage": 100.0 * int(counts.get("accepted", 0)) / total,
                "structural_fingerprints": int(summary["unique_structures"]),
                "rejection_signatures": int(summary["unique_rejections"]),
            }
        )
    return points, problems


def _save(figure: plt.Figure, output_dir: Path, stem: str) -> list[Path]:
    paths = []
    for suffix in ("png", "pdf"):
        path = output_dir / f"{stem}.{suffix}"
        figure.savefig(path)
        paths.append(path)
    plt.close(figure)
    return paths


def _iteration_figure(
    per_run: dict[str, list[dict[str, Any]]],
    metric: str,
    title: str,
    ylabel: str,
    percentage: bool,
) -> plt.Figure | None:
    if not any(per_run.values()):
        return None
    iterations = sorted({point["iteration"] for points in per_run.values() for point in points})
    figure, axes = plt.subplots()
    for index, (run_name, points) in enumerate(sorted(per_run.items())):
        if not points:
            continue
        by_iteration = {point["iteration"]: point[metric] for point in points}
        # None leaves a visible break where an iteration produced no data, rather
        # than interpolating a line across it
        axes.plot(
            iterations,
            [by_iteration.get(iteration) for iteration in iterations],
            label=run_name,
            **_series_style(index),
        )
    axes.set_xlabel("Refinement iteration")
    axes.set_ylabel(ylabel)
    axes.set_title(title)
    axes.set_xticks(iterations)
    if percentage:
        axes.set_ylim(0, 100)
    else:
        axes.set_ylim(bottom=0)
    if len(per_run) > 1:
        axes.legend(ncol=min(3, len(per_run)))
    figure.tight_layout()
    return figure


def _runs_figure(run_names: list[str], values: list[float]) -> plt.Figure | None:
    if not values:
        return None
    figure, axes = plt.subplots()
    positions = range(len(values))
    axes.bar(positions, values, color="0.75", edgecolor="black", linewidth=0.7, width=0.6, zorder=2)
    title_pad = None
    if len(values) > 1:
        mean = statistics.mean(values)
        deviation = statistics.stdev(values)
        axes.axhspan(
            mean - deviation,
            mean + deviation,
            color="0.85",
            zorder=0,
            label=f"$\\pm$1 s.d. = {deviation:.1f}%",
        )
        axes.axhline(mean, color="black", linestyle="--", linewidth=1.0, zorder=3, label=f"mean = {mean:.1f}%")
        # between title and axes: the bars span the full width and the rotated run
        # labels occupy the space below, so neither leaves room for a legend
        axes.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=2)
        title_pad = 22
    axes.set_xticks(list(positions))
    axes.set_xticklabels(run_names, rotation=30, ha="right")
    axes.set_xlabel("Run")
    axes.set_ylabel("Acceptance rate (%)")
    axes.set_title("Acceptance rate across repeated runs", pad=title_pad)
    axes.set_ylim(0, 100)
    figure.tight_layout()
    return figure


def _run_acceptance(root: Path, run_dirs: list[Path]) -> tuple[list[str], list[float]]:
    """Prefer an existing aggregate.json; fall back to the same collection logic."""
    aggregate_path = root / "aggregate.json"
    if aggregate_path.exists():
        try:
            rows = json.loads(aggregate_path.read_text(encoding="utf-8"))["per_run"]
        except (ValueError, OSError, KeyError, TypeError):
            rows = [collect_run(run_dir) for run_dir in run_dirs]
    else:
        rows = [collect_run(run_dir) for run_dir in run_dirs]
    usable = [row for row in rows if row.get("acceptance_percentage") is not None]
    return [str(row["run"]) for row in usable], [float(row["acceptance_percentage"]) for row in usable]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", type=Path, help="directory of run-* dirs, or one run directory")
    parser.add_argument("--output-dir", type=Path, default=None, help="defaults to ROOT/figures")
    args = parser.parse_args()

    run_dirs = find_run_dirs(args.root)
    if not run_dirs:
        raise SystemExit(f"no runs found under {args.root}")

    per_run: dict[str, list[dict[str, Any]]] = {}
    problems: list[str] = []
    for run_dir in run_dirs:
        points, run_problems = read_iterations(run_dir)
        per_run[run_dir.name] = points
        problems.extend(run_problems)

    run_names, acceptance = _run_acceptance(args.root, run_dirs)

    output_dir = args.output_dir or args.root / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    with plt.rc_context(_STYLE):
        figures = [
            (
                "acceptance_rate_per_iteration",
                _iteration_figure(
                    per_run,
                    "acceptance_percentage",
                    "Acceptance rate per refinement iteration",
                    "Acceptance rate (%)",
                    percentage=True,
                ),
            ),
            (
                "structural_fingerprints_per_iteration",
                _iteration_figure(
                    per_run,
                    "structural_fingerprints",
                    "Structural fingerprints per refinement iteration",
                    "Distinct structural fingerprints",
                    percentage=False,
                ),
            ),
            (
                "rejection_signatures_per_iteration",
                _iteration_figure(
                    per_run,
                    "rejection_signatures",
                    "Rejection signatures per refinement iteration",
                    "Distinct rejection signatures",
                    percentage=False,
                ),
            ),
            ("acceptance_rate_across_runs", _runs_figure(run_names, acceptance)),
        ]
        for stem, figure in figures:
            if figure is None:
                problems.append(f"{stem}: skipped, no usable data")
                continue
            written.extend(_save(figure, output_dir, stem))

    for problem in problems:
        print(f"  note: {problem}")
    for path in written:
        print(path)


if __name__ == "__main__":
    main()
