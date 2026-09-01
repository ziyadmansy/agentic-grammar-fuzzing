#!/usr/bin/env python3
"""Run the real agentic refinement loop against the pinned cJSON harness."""

import argparse
import json
import os
from pathlib import Path

from openai import OpenAI

from agentic_fuzzing.llm import OpenAIProposer
from agentic_fuzzing.refinement import run_refinement_loop
from agentic_fuzzing.seeding import build_manifest, resolved_arguments, seed_everything, write_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the bounded cJSON agentic refinement loop")
    parser.add_argument("--executable", default="build/cjson_harness")
    parser.add_argument("--grammar", type=Path, default=Path("grammar/JSON.g4"))
    # defaults to a fresh tree: artifacts/cjson-loop and artifacts/parson-loop hold
    # the single official run the write-up cites and must not be written into.
    parser.add_argument("--artifact-dir", type=Path, default=Path("artifacts/repeated/cjson-loop"))
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--examples", type=int, default=500)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--seed", type=int, default=0, help="seed of the first run; run N uses seed+N-1")
    parser.add_argument("--runs", type=int, default=1, help="number of independent repeated runs")
    parser.add_argument("--overwrite", action="store_true", help="allow writing into a non-empty run directory")
    args = parser.parse_args()

    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY environment variable is not set")

    client = OpenAI(api_key=api_key)
    proposer = OpenAIProposer(client, model=args.model)
    arguments = resolved_arguments(args)

    for run_index in range(args.runs):
        seed = args.seed + run_index
        run_dir = args.artifact_dir / f"run-{run_index + 1:02d}-seed-{seed:04d}"
        if run_dir.exists() and any(run_dir.iterdir()) and not args.overwrite:
            raise SystemExit(f"{run_dir} already contains results; pass --overwrite to replace them")
        run_dir.mkdir(parents=True, exist_ok=True)
        # written before the run so a crashed run still carries its provenance
        write_manifest(run_dir / "manifest.json", build_manifest(seed, arguments, model=args.model))

        seed_everything(seed)
        print(f"== {run_dir} (seed={seed})")
        summaries = run_refinement_loop(
            args.executable,
            args.grammar,
            proposer,
            run_dir,
            iterations=args.iterations,
            examples_per_iteration=args.examples,
            timeout_seconds=args.timeout,
        )
        for index, summary in enumerate(summaries, start=1):
            print(f"iteration-{index}: {summary.as_dict()}")
            # mirror artifacts/parson-loop's layout, which persists summary.json per iteration
            summary_path = run_dir / f"iteration-{index}" / "summary.json"
            summary_path.write_text(json.dumps(summary.as_dict(), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
