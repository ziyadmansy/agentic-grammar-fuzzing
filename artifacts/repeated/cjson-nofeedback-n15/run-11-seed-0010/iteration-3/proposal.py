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
        # Escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape sequence
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))
        # Either safe char or escape sequence
        char_or_escape = st.one_of(
            safe_char.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Compose string content with length limit
        content = st.text(char_or_escape, min_size=0, max_size=20)
        return content.map(lambda s: '"' + s + '"')

    # NUMBER strategy: produce valid JSON numbers as strings
    def json_number():
        # Use Hypothesis floats but convert to JSON number strings
        # Limit floats to finite, non-NaN, non-inf values
        # Also include integers
        int_str = st.integers(min_value=-1_000_000, max_value=1_000_000).map(str)
        float_str = st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ).map(lambda f: format(f, '.6g'))
        return st.one_of(int_str, float_str)

    # Forward declaration for recursive value
    # Use st.recursive to build nested objects and arrays
    base = st.one_of(
        json_string(),
        json_number(),
        json_null,
        json_true,
        json_false,
    )

    # Recursive containers
    def json_obj():
        # pair: STRING ':' value
        pair = st.tuples(json_string(), value).map(lambda p: f"{p[0]}:{p[1]}")
        # object: '{' pair (',' pair)* '}' or '{}'
        return st.lists(pair, max_size=5).map(
            lambda pairs: '{' + (','.join(pairs) if pairs else '') + '}'
        )

    def json_arr():
        # array: '[' value (',' value)* ']' or '[]'
        return st.lists(value, max_size=5).map(
            lambda vals: '[' + (','.join(vals) if vals else '') + ']'
        )

    value = st.recursive(
        base,
        lambda children: st.one_of(json_obj(), json_arr()),
        max_leaves=10,
    )

    # Draw a value and encode as bytes
    s = draw(value)
    return s.encode('utf-8')