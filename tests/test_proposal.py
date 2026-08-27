import pytest

from agentic_fuzzing.proposal import GenerationError, ProposalError, load_strategy, proposal_inputs


def test_loads_bounded_generated_strategy() -> None:
    source = "from hypothesis import strategies as st\n@st.composite\ndef generated_json(draw):\n    return draw(st.just(b'{}'))\n"

    strategy = load_strategy(source)
    assert strategy().example() == b"{}"
    assert list(proposal_inputs(source, 2)) == [b"{}", b"{}"]


def test_rejects_untrusted_imports() -> None:
    with pytest.raises(ProposalError, match="imports"):
        load_strategy("import os\ndef generated_json(draw):\n    return b''\n")


def test_proposal_inputs_yields_generation_error_and_continues() -> None:
    # 2nd draw hits an undefined name (mirrors a real stray-surrogate encode
    # failure): proposal_inputs must log it and keep drawing, not raise.
    source = (
        "from hypothesis import strategies as st\n"
        "calls = []\n"
        "@st.composite\n"
        "def generated_json(draw):\n"
        "    calls.append(1)\n"
        "    if len(calls) == 2:\n"
        "        return undefined_name\n"
        "    return draw(st.just(b'{}'))\n"
    )
    results = list(proposal_inputs(source, 3))
    assert len(results) == 3
    assert isinstance(results[0], GenerationError)
    assert results[1] == b"{}"
    assert results[2] == b"{}"