#!/usr/bin/env python3
"""Build a per-iteration acceptance-rate / structural-diversity table from an
agentic refinement loop's artifact directory (artifacts/<target>-loop/iteration-N/),
in the same format as the parson iteration table in README.md."""

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_dir", type=Path, help="e.g. artifacts/cjson-loop")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    iteration_dirs = sorted(
        (path for path in args.artifact_dir.glob("iteration-*") if path.is_dir()),
        key=lambda path: int(path.name.split("-")[1]),
    )

    rows = ["| Iteration | Accepted / Rejected | Crashes | Structural fingerprints |", "|---|---|---|---|"]
    for iteration_dir in iteration_dirs:
        summary = json.loads((iteration_dir / "summary.json").read_text(encoding="utf-8"))
        counts = summary["counts"]
        if "proposal_rejected" in counts:
            number = iteration_dir.name.split("-")[1]
            error_path = iteration_dir / "proposal_error.txt"
            reason = error_path.read_text(encoding="utf-8").strip() if error_path.exists() else "unknown"
            rows.append(f"| [{number}]({iteration_dir.as_posix()}) | LLM proposal rejected: {reason} | n/a | n/a |")
            continue
        accepted = counts.get("accepted", 0)
        rejected = counts.get("rejected", 0)
        encoding_errors = counts.get("encoding_error", 0)
        crashes = sum(
            value for key, value in counts.items() if key not in {"accepted", "rejected", "encoding_error"}
        )
        total = summary["total"]
        structures = summary["unique_structures"]
        number = iteration_dir.name.split("-")[1]
        encoding_note = f", {encoding_errors} encoding-errors" if encoding_errors else ""
        rows.append(
            f"| [{number}]({iteration_dir.as_posix()}) | {accepted} accepted / {rejected} rejected "
            f"({accepted / total:.1%} acceptance{encoding_note}) | {crashes} | {structures}/{total} |"
        )

    table = "\n".join(rows)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(table + "\n", encoding="utf-8")
        print(args.output)
    else:
        print(table)


if __name__ == "__main__":
    main()
