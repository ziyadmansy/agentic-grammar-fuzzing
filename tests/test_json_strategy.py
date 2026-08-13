import json

from hypothesis import given

from agentic_fuzzing.json_strategy import baseline_json, near_valid_json


@given(baseline_json())
def test_baseline_strategy_emits_valid_json(data: bytes) -> None:
    json.loads(data)


@given(near_valid_json())
def test_near_valid_strategy_is_bytes(data: bytes) -> None:
    assert isinstance(data, bytes)