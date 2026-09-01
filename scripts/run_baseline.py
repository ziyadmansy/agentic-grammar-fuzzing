#!/usr/bin/env python3
import argparse
from pathlib import Path

from agentic_fuzzing.campaign import run_campaign
from agentic_fuzzing.json_strategy import baseline_json, near_valid_json
from agentic_fuzzing.seeding import build_manifest, resolved_arguments, seed_everything, write_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the bounded JSON baseline campaign")
    parser.add_argument("--executable", default="build/cjson_harness")
    parser.add_argument("--examples", type=int, default=50)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--output", type=Path, default=Path("artifacts/baseline.jsonl"))
    parser.add_argument("--seed", type=int, default=0, help="deterministic experiment seed")
    args = parser.parse_args()

    seed_everything(args.seed)

    def input_stream():
        for index in range(args.examples):
            strategy = baseline_json() if index % 2 == 0 else near_valid_json()
            yield strategy.example()

    inputs = input_stream()
    counts = run_campaign(args.executable, inputs, args.output, args.examples, args.timeout)
    manifest_path = write_manifest(
        args.output.with_suffix(".manifest.json"),
        build_manifest(args.seed, resolved_arguments(args)),
    )
    print(dict(counts))
    print(manifest_path)


if __name__ == "__main__":
    main()