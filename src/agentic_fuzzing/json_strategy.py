"""Bounded JSON strategies derived from grammar/JSON.g4."""

import json

from hypothesis import strategies as st


json_scalar = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-10**12, max_value=10**12),
    st.floats(allow_nan=False, allow_infinity=False, width=64),
    st.text(max_size=80),
)


json_value = st.recursive(
    json_scalar,
    lambda children: st.one_of(
        st.lists(children, max_size=8),
        st.dictionaries(st.text(max_size=40), children, max_size=8),
    ),
    max_leaves=32,
)


@st.composite
def baseline_json(draw: st.DrawFn) -> bytes:
    """Generate bounded, grammar-valid JSON documents as UTF-8 bytes."""
    value = draw(json_value)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


@st.composite
def near_valid_json(draw: st.DrawFn) -> bytes:
    """Create a small malformed neighbor of a grammar-valid document."""
    document = draw(baseline_json())
    mutation = draw(st.sampled_from((b",", b"]", b"}", b" trailing", b"\x00")))
    return document + mutation