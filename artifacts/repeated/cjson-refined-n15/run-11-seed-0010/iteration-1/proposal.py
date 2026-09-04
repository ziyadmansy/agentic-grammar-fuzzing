from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # JSON string with safe codepoints and escapes
    # We'll use a simplified string strategy that produces valid JSON strings
    json_string = st.text(
        alphabet=(
            # safe codepoints excluding control chars and quotes/backslash
            ''.join(chr(c) for c in range(0x20, 0x7F) if c not in (0x22, 0x5C))
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # Recursive JSON value strategy
    # Use st.recursive to build nested arrays and objects with bounded depth and size
    base = st.one_of(json_string, json_number, json_null, json_true, json_false)

    def json_object():
        # pair: STRING ':' value
        pair = st.tuples(json_string, json_value).map(lambda p: f"{p[0]}:{p[1]}")
        # object: '{' pair (',' pair)* '}' or '{}'
        # limit number of pairs to keep size bounded
        return st.lists(pair, max_size=3).map(
            lambda pairs: "{" + ",".join(pairs) + "}" if pairs else "{}"
        )

    def json_array():
        # array: '[' value (',' value)* ']' or '[]'
        return st.lists(json_value, max_size=3).map(
            lambda values: "[" + ",".join(values) + "]" if values else "[]"
        )

    # We need to define json_value here to use in json_object and json_array
    # Use st.deferred to allow recursion
    json_value = st.deferred(lambda: st.one_of(
        base,
        json_object(),
        json_array(),
    ))

    # Draw a json_value and append EOF (which is nothing)
    result = draw(json_value)
    return result.encode("utf-8")