from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # JSON strings: use Hypothesis text with safe codepoints, escape quotes and backslashes
    def json_string(s: str) -> str:
        # Escape backslash and quote for JSON string
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        # Also escape control characters (U+0000 to U+001F) as \uXXXX
        def escape_ctrl(c):
            if ord(c) < 0x20:
                return "\\u%04x" % ord(c)
            return c
        s = "".join(escape_ctrl(c) for c in s)
        return f'"{s}"'
    json_string_strat = st.text(
        alphabet=st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=20,
    ).map(json_string)

    # Recursive strategy for JSON values
    # We limit max_leaves to keep size bounded
    json_value = st.deferred(lambda: json_value_strat)

    # Object pairs: STRING : value
    json_pair = st.tuples(json_string_strat, json_value).map(lambda p: f"{p[0]}:{p[1]}")

    # Object: { pair (, pair)* } or {}
    json_object = st.lists(json_pair, max_size=5).map(
        lambda pairs: "{" + (",".join(pairs) if pairs else "") + "}"
    )

    # Array: [ value (, value)* ] or []
    json_array = st.lists(json_value, max_size=5).map(
        lambda values: "[" + (",".join(values) if values else "") + "]"
    )

    # Compose the recursive value strategy
    json_value_strat = st.recursive(
        st.one_of(json_null, json_true, json_false, json_number, json_string_strat),
        lambda children: st.one_of(json_object, json_array),
        max_leaves=10,
    )

    # Draw a JSON value and encode as bytes
    result = draw(json_value)
    return result.encode("utf-8")