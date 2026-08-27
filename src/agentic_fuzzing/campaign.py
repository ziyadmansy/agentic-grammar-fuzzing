"""Run a bounded baseline campaign and write JSONL observations."""

from collections import Counter
import json
from pathlib import Path
from typing import Iterable

from .runner import RunResult, run_input
from .triage import sanitizer_signature, signature_id
from .proposal import GenerationError


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
            if isinstance(data, GenerationError):
                # a single bad Hypothesis draw (e.g. an unencodable surrogate) must
                # not abort the rest of the campaign -- log it and keep going.
                counts["encoding_error"] += 1
                output.write(json.dumps(_generation_error_observation(index, data)) + "\n")
                continue
            result = run_input(executable, data, timeout_seconds)
            counts[result.status] += 1
            output.write(json.dumps(_observation(index, data, result)) + "\n")
    return counts


def _generation_error_observation(index: int, error: GenerationError) -> dict[str, object]:
    return {
        "index": index,
        "input_hex": "",
        "input_length": 0,
        "status": "encoding_error",
        "returncode": None,
        "stdout": "",
        "stderr": "",
        "rejection_signature": None,
        "sanitizer_signature": None,
        "crash_id": None,
        "structure": "",
        "generation_error": error.error,
    }


def _observation(index: int, data: bytes, result: RunResult) -> dict[str, object]:
    stdout = result.stdout.decode("utf-8", errors="replace")
    stderr = result.stderr.decode("utf-8", errors="replace")
    return {
        "index": index,
        "input_hex": data.hex(),
        "input_length": len(data),
        "status": result.status,
        "returncode": result.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "rejection_signature": stdout if result.status == "rejected" else None,
        "sanitizer_signature": sanitizer_signature(result.stderr) if result.status == "crash" else None,
        "crash_id": signature_id(result.stderr) if result.status == "crash" else None,
        "structure": _structure(data),
    }


def _structure(data: bytes) -> str:
    """Return a stable, parser-independent shape fingerprint for diversity metrics."""
    categories = []
    for byte in data:
        if byte in b"{}[]:,":
            categories.append(chr(byte))
        elif byte in b" \t\r\n":
            categories.append("_")
        elif 48 <= byte <= 57:
            categories.append("#")
        elif byte == 34:
            categories.append('"')
        else:
            categories.append("x")
    return "".join(categories[:256])