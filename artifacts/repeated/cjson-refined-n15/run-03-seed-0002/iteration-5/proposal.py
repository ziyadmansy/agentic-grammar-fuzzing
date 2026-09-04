from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string with safe codepoints and escapes
    # SAFECODEPOINT ~["\\\u0000-\u001F], so exclude control chars and backslash and quote
    # We'll allow common escapes as well
    def json_string():
        # Characters allowed inside strings (excluding control chars, backslash, quote)
        safe_chars = st.characters(
            blacklist_characters=['\\', '"'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escape sequences
        escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \uXXXX
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))

        # Build string content: mix of safe chars, escapes, unicode escapes
        # To keep near-valid, allow some escapes and unicode escapes
        string_char = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Generate 0 to 20 chars inside string
        content = st.lists(string_char, max_size=20).map(''.join)
        return content.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # JSON number
    # Use Hypothesis built-in floats, but convert to JSON number string format
    def json_number():
        # Generate floats and ints, then convert to JSON number strings
        # Limit floats to finite, non-NaN, non-inf
        # Also generate integers as strings
        int_str = st.integers(min_value=-10**6, max_value=10**6).map(str)
        float_str = st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ).map(lambda f: format(f, '.6g'))  # compact representation
        return st.one_of(int_str, float_str)

    json_number_st = json_number()

    # Recursive JSON value
    # We'll use st.recursive to build nested objects and arrays

    # Forward declaration for value
    # value = STRING | NUMBER | obj | arr | true | false | null

    # Define obj and arr recursively
    def json_value():
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_null,
            json_true,
            json_false,
        )

        # obj: '{' pair (',' pair)* '}' | '{}'
        # pair: STRING ':' value
        def json_pair():
            return st.tuples(json_string_st, json_value()).map(lambda p: f"{p[0]}:{p[1]}")

        json_obj = st.recursive(
            base,
            lambda children: st.one_of(
                # object with pairs
                st.lists(json_pair(), max_size=5).map(
                    lambda pairs: "{" + ",".join(pairs) + "}"
                ),
                # array with values
                st.lists(children, max_size=5).map(
                    lambda vals: "[" + ",".join(vals) + "]"
                ),
            ),
            max_leaves=10,
        )
        return json_obj

    # Generate the full JSON text, then encode as bytes
    json_text = json_value()

    s = draw(json_text)
    return s.encode("utf-8")