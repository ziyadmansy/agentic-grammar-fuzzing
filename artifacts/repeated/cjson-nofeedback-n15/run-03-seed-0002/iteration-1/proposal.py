from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    def json_string():
        # Characters allowed inside strings (excluding control chars and " \)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escape sequences
        escape_seq = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t'
        ])
        # Unicode escape: \uXXXX
        hex_digit = st.sampled_from("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: "".join(t))

        # Either a safe char, or an escape sequence
        char = st.one_of(
            safe_char.map(lambda c: c),
            escape_seq,
            unicode_escape,
        )

        # Compose string content with length 0 to 20 to keep size bounded
        content = st.lists(char, max_size=20).map("".join)
        return content.map(lambda s: f'"{s}"')

    # NUMBER strategy: produce valid JSON numbers
    def json_number():
        # Use Hypothesis built-in floats and convert to JSON number strings
        # Limit floats to finite, non-NaN, non-infinite
        # Also include integers
        int_str = st.integers(min_value=-10**6, max_value=10**6).map(str)
        float_str = st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ).map(lambda f: format(f, '.6g'))  # compact representation
        return st.one_of(int_str, float_str)

    # Recursive JSON value strategy
    # We use st.recursive to build nested arrays and objects with bounded depth and size
    base = st.one_of(
        json_string(),
        json_number(),
        json_null,
        json_true,
        json_false,
    )

    # Forward declarations for recursive use
    # obj: '{' pair (',' pair)* '}' | '{}'
    # pair: STRING ':' value
    # arr: '[' value (',' value)* ']' | '[]'

    # We'll define pair and value inside the recursive function

    def json_value():
        # We define pair here to avoid forward reference issues
        @st.composite
        def pair(draw):
            k = draw(json_string())
            v = draw(value)
            return f"{k}:{v}"

        # Objects: either empty or with 1-5 pairs
        json_obj = st.one_of(
            st.just("{}"),
            st.lists(pair(), min_size=1, max_size=5).map(lambda pairs: "{" + ",".join(pairs) + "}")
        )

        # Arrays: either empty or with 1-5 values
        json_arr = st.one_of(
            st.just("[]"),
            st.lists(value, min_size=1, max_size=5).map(lambda vals: "[" + ",".join(vals) + "]")
        )

        return st.one_of(base, json_obj, json_arr)

    value = st.recursive(base, lambda children: json_value(), max_leaves=10)

    # Draw the full JSON value and append EOF (nothing)
    result = draw(value)
    return result.encode("utf-8")