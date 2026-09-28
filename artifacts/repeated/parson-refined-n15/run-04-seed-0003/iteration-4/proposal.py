from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # String strategy: safe codepoints excluding control chars and quotes/backslash
    # Use a small max size to keep examples bounded
    json_string = st.text(
        alphabet=(
            # all unicode except control chars (U+0000-U+001F), quote, backslash
            # Hypothesis text() excludes surrogates by default
            # We'll filter out quote and backslash explicitly
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # Number strategy: generate floats and ints, format as JSON number strings
    def json_number_str(n):
        # Format float or int as JSON number string
        # Use repr to get a valid JSON number representation
        # Avoid trailing .0 for ints
        if isinstance(n, int):
            return str(n)
        else:
            # Use repr to get exponent notation if needed
            return repr(n)

    json_number = st.one_of(
        st.integers(min_value=-10**6, max_value=10**6),
        st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ),
    ).map(json_number_str)

    # Recursive JSON value strategy
    # Use st.recursive to build nested objects and arrays with bounded depth and size
    base = st.one_of(json_null, json_true, json_false, json_string, json_number)

    def json_object():
        # pair: STRING ':' value
        # Use small max size to keep examples bounded
        pair = st.tuples(json_string, generated_json_value).map(lambda p: f"{p[0]}:{p[1]}")
        # object: '{' pair (',' pair)* '}' or '{}'
        return st.lists(pair, max_size=5).map(
            lambda pairs: "{" + ",".join(pairs) + "}" if pairs else "{}"
        )

    def json_array():
        # array: '[' value (',' value)* ']' or '[]'
        return st.lists(generated_json_value, max_size=5).map(
            lambda values: "[" + ",".join(values) + "]" if values else "[]"
        )

    generated_json_value = st.recursive(
        base,
        lambda children: st.one_of(json_object(), json_array()),
        max_leaves=10,
    )

    # Draw a JSON value and encode as UTF-8 bytes
    s = draw(generated_json_value)
    return s.encode("utf-8")