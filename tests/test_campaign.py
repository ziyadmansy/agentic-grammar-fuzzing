import json
import sys

from agentic_fuzzing.campaign import run_campaign
from agentic_fuzzing.proposal import GenerationError


def test_campaign_is_bounded_and_persists_observations(tmp_path) -> None:
    output = tmp_path / "results.jsonl"
    counts = run_campaign(sys.executable, [b"", b""], output, max_examples=1)

    assert counts["rejected"] == 1
    records = output.read_text(encoding="utf-8").splitlines()
    assert len(records) == 1
    assert json.loads(records[0])["input_length"] == 0


def test_campaign_logs_generation_error_and_continues(tmp_path) -> None:
    output = tmp_path / "results.jsonl"
    inputs = [GenerationError("boom"), b""]
    counts = run_campaign(sys.executable, inputs, output, max_examples=2)

    assert counts["encoding_error"] == 1
    assert counts["rejected"] == 1
    records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert records[0]["status"] == "encoding_error"
    assert records[0]["generation_error"] == "boom"
    assert records[1]["status"] == "rejected"