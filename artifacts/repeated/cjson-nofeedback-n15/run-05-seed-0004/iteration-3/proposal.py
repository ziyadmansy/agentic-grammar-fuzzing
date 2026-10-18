from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode them as JSON strings.
    # To keep it simple, use st.text with safe characters and escape quotes/backslashes.
    def json_string():
        # safe characters exclude control chars and backslash and quote
        safe_chars = (
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # Compose a string with length 0 to 20
        s = st.text(safe_chars, min_size=0, max_size=20)
        # Escape backslash and quote
        def to_json_str(x: str) -> str:
            # Escape backslash and quote and control chars
            def esc_char(c):
                if c == '"':
                    return '\\"'
                elif c == '\\':
                    return '\\\\'
                elif c == '\b':
                    return '\\b'
                elif c == '\f':
                    return '\\f'
                elif c == '\n':
                    return '\\n'
                elif c == '\r':
                    return '\\r'
                elif c == '\t':
                    return '\\t'
                elif ord(c) < 0x20:
                    # Unicode escape for control chars
                    return '\\u%04x' % ord(c)
                else:
                    return c
            return '"' + ''.join(esc_char(c) for c in x) + '"'

        return s.map(to_json_str)

    json_string_st = json_string()

    # NUMBER strategy: produce valid JSON numbers as strings
    # Use hypothesis floats but convert to JSON number strings carefully
    def json_number():
        # Generate floats and ints, convert to JSON number strings
        # Limit floats to finite range and avoid NaN/inf
        # Also generate ints as strings
        int_str = st.integers(min_value=-10**6, max_value=10**6).map(str)
        float_str = st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ).map(lambda f: format(f, '.15g'))  # remove trailing zeros smartly
        return st.one_of(int_str, float_str)

    json_number_st = json_number()

    # Recursive JSON value strategy
    # Use st.recursive to build nested objects and arrays
    base = st.one_of(
        json_string_st,
        json_number_st,
        json_null,
        json_true,
        json_false,
    )

    # Pair: STRING ':' value
    @st.composite
    def json_pair(draw):
        k = draw(json_string_st)
        # Remove the quotes from the key string for the pair, but keep quotes in output
        # Actually, keys must be strings, so keep quotes
        v = draw(value)
        return f"{k}:{v}"

    # Object: '{' pair (',' pair)* '}' or '{}'
    @st.composite
    def json_object(draw):
        # Generate 0 to 5 pairs
        pairs = draw(st.lists(json_pair(), min_size=0, max_size=5))
        if not pairs:
            return "{}"
        return "{" + ",".join(pairs) + "}"

    # Array: '[' value (',' value)* ']' or '[]'
    @st.composite
    def json_array(draw):
        # Generate 0 to 5 values
        values = draw(st.lists(value, min_size=0, max_size=5))
        if not values:
            return "[]"
        return "[" + ",".join(values) + "]"

    # Compose value recursively
    value = st.recursive(
        base,
        lambda children: st.one_of(
            json_object(),
            json_array(),
        ),
        max_leaves=10,
    )

    # Draw the final JSON value and append EOF (nothing)
    result = draw(value)
    # Return as bytes
    return result.encode("utf-8")