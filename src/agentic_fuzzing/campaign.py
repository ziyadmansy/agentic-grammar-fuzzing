"""Run a bounded baseline campaign and write JSONL observations."""

from collections import Counter
import json
from pathlib import Path
from typing import Iterable

from .runner import RunResult, run_input


def run_campaign(
    executable: str,
    inputs: Iterable[bytes],
    output_path: Path,
    max_examples: int = 500,
    timeout_seconds: float = 5.0,
) -> Counter[str]:
    """Run at most ``max_examples`` and persist every result as one JSON line."""
    counts: Counter[str] = Counter()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output:
        for index, data in enumerate(inputs):
            if index >= max_examples:
                break
            result = run_input(executable, data, timeout_seconds)
            counts[result.status] += 1
            output.write(json.dumps(_observation(index, data, result)) + "\n")
    return counts


def _observation(index: int, data: bytes, result: RunResult) -> dict[str, object]:
    return {
        "index": index,
        "input_hex": data.hex(),
        "input_length": len(data),
        "status": result.status,
        "returncode": result.returncode,
        "stdout": result.stdout.decode("utf-8", errors="replace"),
        "stderr": result.stderr.decode("utf-8", errors="replace"),
    }