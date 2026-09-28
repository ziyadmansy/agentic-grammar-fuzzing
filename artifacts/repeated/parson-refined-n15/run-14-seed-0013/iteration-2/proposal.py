from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives as strings
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.from_regex(
        r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?",
        fullmatch=True,
    )
    # JSON string with safe codepoints and escapes
    json_string = st.text(
        alphabet=(
            # safe codepoints excluding control chars and " \ 
            # (0x20-0x21, 0x23-0x5B, 0x5D-0x10FFFF)
            # We'll just exclude control chars and backslash and quote
            # Hypothesis text default includes surrogate pairs, which is fine
            # but we exclude control chars and backslash and quote explicitly
            # by filtering
        ),
        min_size=0,
        max_size=20,
    ).filter(
        lambda s: all(
            (c != '"' and c != '\\' and ord(c) >= 0x20 and ord(c) != 0x7F)
            for c in s
        )
    ).map(lambda s: '"' + s + '"')

    # Recursive JSON values
    # We build a strategy for JSON values as strings (not parsed objects)
    # to produce valid JSON text.

    # Forward declaration for recursive use
    def json_value():
        return st.deferred(lambda: json_value_strategy)

    # JSON array: [ value (, value)* ]
    json_array = st.lists(json_value(), min_size=0, max_size=3).map(
        lambda vs: "[" + ",".join(vs) + "]"
    )

    # JSON object: { pair (, pair)* }
    # pair = STRING : value
    json_pair = st.tuples(json_string, json_value()).map(
        lambda kv: kv[0] + ":" + kv[1]
    )
    json_object = st.lists(json_pair, min_size=0, max_size=3).map(
        lambda pairs: "{" + ",".join(pairs) + "}"
    )

    json_value_strategy = st.one_of(
        json_string,
        json_number,
        json_object,
        json_array,
        json_true,
        json_false,
        json_null,
    )

    # Draw a JSON value string
    s = draw(json_value_strategy)
    return s.encode("utf-8")