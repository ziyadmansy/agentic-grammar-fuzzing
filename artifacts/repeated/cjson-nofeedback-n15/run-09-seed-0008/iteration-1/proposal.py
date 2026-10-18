from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    def json_string():
        # Characters allowed inside strings (excluding control chars and quotes/backslash)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape sequences
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))
        # Either a safe char or an escape sequence
        string_char = st.one_of(
            safe_char.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Build string content with length bounded to keep size reasonable
        content = st.text(string_char, min_size=0, max_size=20)
        return content.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # NUMBER strategy: use Hypothesis floats and ints formatted as JSON numbers
    def json_number():
        # Generate numbers as strings matching the grammar
        # Use floats and ints, exclude infinities and NaNs
        number = st.one_of(
            st.integers(min_value=-10**6, max_value=10**6).map(str),
            st.floats(
                min_value=-1e6,
                max_value=1e6,
                allow_infinity=False,
                allow_nan=False,
                width=32,
            ).map(lambda f: format(f, '.6g'))
        )
        return number

    json_number_st = json_number()

    # Recursive JSON value strategy
    # We'll define a recursive strategy for value, obj, arr

    # Forward declaration to allow recursion
    json_value = st.deferred(lambda: json_value_inner)

    # JSON pair: STRING : value
    json_pair = st.tuples(json_string_st, json_value).map(lambda t: f"{t[0]}:{t[1]}")

    # JSON object
    def json_object():
        # Either empty or with 1-3 pairs
        pairs = st.lists(json_pair, min_size=0, max_size=3)
        return pairs.map(lambda ps: "{" + ",".join(ps) + "}")

    json_object_st = json_object()

    # JSON array
    def json_array():
        # Either empty or with 1-5 values
        values = st.lists(json_value, min_size=0, max_size=5)
        return values.map(lambda vs: "[" + ",".join(vs) + "]")

    json_array_st = json_array()

    # Compose the value strategy
    json_value_inner = st.one_of(
        json_string_st,
        json_number_st,
        json_object_st,
        json_array_st,
        json_true,
        json_false,
        json_null,
    )

    # Generate the full JSON text and encode as bytes
    result = draw(json_value)
    return result.encode("utf-8")