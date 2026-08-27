#!/usr/bin/env python3
"""Run the real agentic refinement loop against the pinned cJSON harness."""

import argparse
import json
import os
from pathlib import Path

from openai import OpenAI

from agentic_fuzzing.llm import OpenAIProposer
from agentic_fuzzing.refinement import run_refinement_loop


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the bounded cJSON agentic refinement loop")
    parser.add_argument("--executable", default="build/cjson_harness")
    parser.add_argument("--grammar", type=Path, default=Path("grammar/JSON.g4"))
    parser.add_argument("--artifact-dir", type=Path, default=Path("artifacts/cjson-loop"))
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--examples", type=int, default=500)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--model", default="gpt-4.1-mini")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY environment variable is not set")

    client = OpenAI(api_key=api_key)
    proposer = OpenAIProposer(client, model=args.model)

    summaries = run_refinement_loop(
        args.executable,
        args.grammar,
        proposer,
        args.artifact_dir,
        iterations=args.iterations,
        examples_per_iteration=args.examples,
        timeout_seconds=args.timeout,
    )
    for index, summary in enumerate(summaries, start=1):
        print(f"iteration-{index}: {summary.as_dict()}")
        # mirror artifacts/parson-loop's layout, which persists summary.json per iteration
        summary_path = args.artifact_dir / f"iteration-{index}" / "summary.json"
        summary_path.write_text(json.dumps(summary.as_dict(), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
