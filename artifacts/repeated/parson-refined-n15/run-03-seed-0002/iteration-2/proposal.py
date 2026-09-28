from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON strings: use ASCII printable except control chars and backslash/quote,
    # with some escapes to cover ESC and UNICODE
    def json_string():
        # safe codepoints exclude control chars and backslash/quote
        safe_chars = st.characters(
            blacklist_characters=['\\', '"'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # We include some escapes for coverage
        escapes = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t',
            # unicode escape with 4 hex digits
            r'\u1234', r'\uabcd', r'\u0000', r'\uffff',
        ])
        # Compose string parts: mostly safe chars, sometimes escapes
        parts = st.lists(
            st.one_of(
                safe_chars.map(lambda c: c),
                escapes,
            ),
            min_size=0,
            max_size=20,
        )
        s = draw(parts)
        # Join parts, then wrap in quotes
        joined = ''.join(s)
        return f'"{joined}"'

    json_string_st = st.deferred(json_string)

    # JSON numbers: use Hypothesis floats converted to JSON number strings
    # but restrict to finite numbers, no NaN or inf
    def json_number():
        # Generate numbers as strings matching grammar
        # We'll generate floats and convert to string with minimal formatting
        # Also generate integers as strings
        int_str = st.integers(min_value=-10**6, max_value=10**6).map(str)
        float_str = st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ).map(lambda f: format(f, '.6g'))  # compact float representation
        # Also generate numbers with exponent explicitly
        def with_exp():
            base = draw(st.floats(
                allow_nan=False,
                allow_infinity=False,
                width=32,
                min_value=1e-6,
                max_value=1e6,
            ))
            exp = draw(st.integers(min_value=-10, max_value=10))
            s = f"{base:.6g}e{exp:+d}"
            return s
        return st.one_of(int_str, float_str, st.deferred(with_exp))

    json_number_st = json_number()

    # Forward declaration for recursive structures
    json_value = st.deferred(lambda: value_st)

    # JSON pair: STRING ':' value
    @st.composite
    def json_pair(draw):
        key = draw(json_string_st)
        val = draw(json_value)
        return f"{key}:{val}"

    # JSON object: '{' pair (',' pair)* '}' or '{}'
    @st.composite
    def json_object(draw):
        # limit number of pairs to keep size bounded
        pairs = draw(st.lists(json_pair(), max_size=5))
        if not pairs:
            return "{}"
        return "{" + ",".join(pairs) + "}"

    # JSON array: '[' value (',' value)* ']' or '[]'
    @st.composite
    def json_array(draw):
        values = draw(st.lists(json_value, max_size=5))
        if not values:
            return "[]"
        return "[" + ",".join(values) + "]"

    # Compose the recursive value strategy with bounded recursion
    value_st = st.recursive(
        st.one_of(
            json_string_st,
            json_number_st,
            json_null,
            json_true,
            json_false,
        ),
        lambda children: st.one_of(
            json_object(),
            json_array(),
        ),
        max_leaves=10,
    )

    # Generate the full JSON text and encode as bytes
    json_text = draw(value_st)
    return json_text.encode("utf-8")