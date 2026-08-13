#!/usr/bin/env python3
import argparse
from pathlib import Path

from agentic_fuzzing.campaign import run_campaign
from agentic_fuzzing.json_strategy import baseline_json, near_valid_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the bounded JSON baseline campaign")
    parser.add_argument("--executable", default="build/cjson_harness")
    parser.add_argument("--examples", type=int, default=50)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--output", type=Path, default=Path("artifacts/baseline.jsonl"))
    args = parser.parse_args()

    def input_stream():
        for index in range(args.examples):
            strategy = baseline_json() if index % 2 == 0 else near_valid_json()
            yield strategy.example()

    inputs = input_stream()
    counts = run_campaign(args.executable, inputs, args.output, args.examples, args.timeout)
    print(dict(counts))


if __name__ == "__main__":
    main()