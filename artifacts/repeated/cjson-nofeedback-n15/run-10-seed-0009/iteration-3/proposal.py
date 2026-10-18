from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # STRING: simplified safe string with escapes
    json_string = st.text(
        alphabet=(
            # safe codepoints excluding control chars and backslash and quote
            ''.join(chr(c) for c in range(0x20, 0x7F) if c not in (0x22, 0x5C))
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # Recursive JSON value
    # Use recursive to bound depth and size
    json_value = st.deferred(lambda: json_value_inner)

    # JSON object: { pair (, pair)* } or {}
    # pair: STRING : value
    json_pair = st.tuples(json_string, json_value).map(lambda p: f"{p[0]}:{p[1]}")

    json_obj = st.recursive(
        st.just("{}"),
        lambda children: st.builds(
            lambda pairs: "{" + ",".join(pairs) + "}",
            st.lists(json_pair, min_size=1, max_size=3),
        ),
        max_leaves=3,
    )

    # JSON array: [ value (, value)* ] or []
    json_arr = st.recursive(
        st.just("[]"),
        lambda children: st.builds(
            lambda values: "[" + ",".join(values) + "]",
            st.lists(json_value, min_size=1, max_size=3),
        ),
        max_leaves=3,
    )

    json_value_inner = st.one_of(
        json_string,
        json_number,
        json_obj,
        json_arr,
        json_true,
        json_false,
        json_null,
    )

    # Draw a full JSON value and encode as bytes
    result = draw(json_value)
    return result.encode("utf-8")