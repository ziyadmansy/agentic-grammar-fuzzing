import pytest

from agentic_fuzzing.proposal import ProposalError, load_strategy, proposal_inputs


def test_loads_bounded_generated_strategy() -> None:
    source = "from hypothesis import strategies as st\n@st.composite\ndef generated_json(draw):\n    return draw(st.just(b'{}'))\n"

    strategy = load_strategy(source)
    assert strategy().example() == b"{}"
    assert list(proposal_inputs(source, 2)) == [b"{}", b"{}"]


def test_rejects_untrusted_imports() -> None:
    with pytest.raises(ProposalError, match="imports"):
        load_strategy("import os\ndef generated_json(draw):\n    return b''\n")