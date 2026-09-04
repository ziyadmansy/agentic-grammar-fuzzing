#!/usr/bin/env python3
"""Render the paper's baseline-vs-refined acceptance-rate comparison figure.

Reads only <baseline-dir>/aggregate.json and <refined-dir>/aggregate.json
(never results.jsonl, and imports no fuzzing code), matching the read-only
convention of scripts/make_figures.py, and writes
paper/figures/acceptance_comparison.{png,pdf}. Defaults to
artifacts/final/{baseline,refined}, the original five-seed comparison; pass
--baseline-dir/--refined-dir to render a different arm pair (e.g. the
fifteen-seed artifacts/repeated/cjson-{baseline,refined}-n15 comparison).
"""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STYLE = {
    "figure.figsize": (5.5, 3.2),
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
    "axes.axisbelow": True,
    "axes.spines.top": False,
    "axes.spines.right": False,
}


def per_run_acceptance(directory: Path) -> list[float]:
    data = json.loads((directory / "aggregate.json").read_text())
    return [run["acceptance_percentage"] for run in data["per_run"]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-dir", type=Path, default=ROOT / "artifacts" / "final" / "baseline")
    parser.add_argument("--refined-dir", type=Path, default=ROOT / "artifacts" / "final" / "refined")
    args = parser.parse_args()

    plt.rcParams.update(STYLE)
    baseline = per_run_acceptance(args.baseline_dir)
    refined = per_run_acceptance(args.refined_dir)
    n = len(baseline)
    assert n == len(refined)

    x = range(1, n + 1)
    width = 0.35
    fig, ax = plt.subplots(figsize=(8.5, 3.2) if n > 8 else (5.5, 3.2))
    ax.bar([i - width / 2 for i in x], baseline, width, label="Baseline", color="0.65", edgecolor="0.2")
    ax.bar([i + width / 2 for i in x], refined, width, label="Refined", color="0.2", edgecolor="0.2")
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{i - 1}" for i in x])
    ax.set_xlabel("Run (seed)")
    ax.set_ylabel("Acceptance rate (%)")
    ax.set_ylim(0, 105)
    ax.set_title("cJSON acceptance rate: baseline vs. LLM-refined, per run")
    ax.legend(loc="lower right")

    out_dir = ROOT / "paper" / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(out_dir / f"acceptance_comparison.{ext}")
    plt.close(fig)
    print(f"wrote {out_dir}/acceptance_comparison.{{png,pdf}}")


if __name__ == "__main__":
    main()
