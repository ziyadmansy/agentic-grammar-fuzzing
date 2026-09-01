#!/usr/bin/env python3
"""Grammar-only baseline campaigns: the same pipeline as the refinement loop with
no LLM and no refinement, so the two are directly comparable.

`--artifact-dir` switches from the original single-file campaign to the run
layout the refined experiments use (run-NN-seed-SSSS/iteration-1/), which the
aggregation and figure tooling reads unchanged. A baseline run has exactly one
iteration because there is nothing to refine.
"""

import argparse
import json
from pathlib import Path

from agentic_fuzzing.campaign import run_campaign
from agentic_fuzzing.json_strategy import baseline_json, near_valid_json
from agentic_fuzzing.refinement import summarize_records
from agentic_fuzzing.seeding import build_manifest, resolved_arguments, seed_everything, write_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the bounded JSON baseline campaign")
    parser.add_argument("--executable", default="build/cjson_harness")
    parser.add_argument("--examples", type=int, default=50)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--output", type=Path, default=Path("artifacts/baseline.jsonl"))
    parser.add_argument("--seed", type=int, default=0, help="seed of the first run; run N uses seed+N-1")
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="write run-NN-seed-SSSS/iteration-1/ runs here instead of a single --output file",
    )
    parser.add_argument("--runs", type=int, default=1, help="repeated runs; requires --artifact-dir")
    parser.add_argument("--overwrite", action="store_true", help="allow writing into a non-empty run directory")
    args = parser.parse_args()

    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")
    if args.runs > 1 and args.artifact_dir is None:
        raise SystemExit("--runs requires --artifact-dir")

    def input_stream():
        for index in range(args.examples):
            strategy = baseline_json() if index % 2 == 0 else near_valid_json()
            yield strategy.example()

    if args.artifact_dir is None:
        seed_everything(args.seed)
        counts = run_campaign(args.executable, input_stream(), args.output, args.examples, args.timeout)
        manifest_path = write_manifest(
            args.output.with_suffix(".manifest.json"),
            build_manifest(args.seed, resolved_arguments(args)),
        )
        print(dict(counts))
        print(manifest_path)
        return

    arguments = resolved_arguments(args)
    for run_index in range(args.runs):
        seed = args.seed + run_index
        run_dir = args.artifact_dir / f"run-{run_index + 1:02d}-seed-{seed:04d}"
        if run_dir.exists() and any(run_dir.iterdir()) and not args.overwrite:
            raise SystemExit(f"{run_dir} already contains results; pass --overwrite to replace them")
        iteration_dir = run_dir / "iteration-1"
        iteration_dir.mkdir(parents=True, exist_ok=True)
        # written before the run so a crashed run still carries its provenance
        write_manifest(run_dir / "manifest.json", build_manifest(seed, arguments))

        seed_everything(seed)
        print(f"== {run_dir} (seed={seed})")
        result_path = iteration_dir / "results.jsonl"
        run_campaign(args.executable, input_stream(), result_path, args.examples, args.timeout)
        with result_path.open(encoding="utf-8") as result_file:
            summary = summarize_records(json.loads(line) for line in result_file)
        (iteration_dir / "summary.json").write_text(
            json.dumps(summary.as_dict(), indent=2) + "\n", encoding="utf-8"
        )
        print(f"iteration-1: {summary.as_dict()}")


if __name__ == "__main__":
    main()