import json
import sys

from agentic_fuzzing.campaign import run_campaign


def test_campaign_is_bounded_and_persists_observations(tmp_path) -> None:
    output = tmp_path / "results.jsonl"
    counts = run_campaign(sys.executable, [b"", b""], output, max_examples=1)

    assert counts["rejected"] == 1
    records = output.read_text(encoding="utf-8").splitlines()
    assert len(records) == 1
    assert json.loads(records[0])["input_length"] == 0