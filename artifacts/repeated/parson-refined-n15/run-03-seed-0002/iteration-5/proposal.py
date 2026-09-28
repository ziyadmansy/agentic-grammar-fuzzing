from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # JSON strings: use ASCII printable except control chars and backslash/quote
    json_string = st.text(
        st.characters(
            blacklist_characters=['\\', '"'],
            blacklist_categories=('Cc',),  # control chars
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        max_size=20,
    ).map(lambda s: '"' + s + '"')

    # Recursive JSON value strategy
    # Use st.recursive to build nested arrays and objects
    base = st.one_of(json_string, json_number, json_null, json_true, json_false)

    def json_obj():
        # pair: STRING ':' value
        pair = st.tuples(json_string, json_value).map(lambda p: f"{p[0]}:{p[1]}")
        # object: '{' pair (',' pair)* '}' or '{}'
        return st.lists(pair, max_size=5).map(
            lambda pairs: "{" + (",".join(pairs) if pairs else "") + "}"
        )

    def json_arr():
        # array: '[' value (',' value)* ']' or '[]'
        return st.lists(json_value, max_size=5).map(
            lambda values: "[" + (",".join(values) if values else "") + "]"
        )

    # Use st.deferred to allow recursion
    json_value = st.deferred(lambda: st.one_of(
        base,
        json_obj(),
        json_arr(),
    ))

    # Draw a JSON value and encode as bytes
    s = draw(json_value)
    return s.encode("utf-8")