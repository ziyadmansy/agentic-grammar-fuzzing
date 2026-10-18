from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with safe codepoints and escapes
    # Use a small subset of escapes to keep near-valid cases
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escapes: simple ones and unicode escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \uXXXX with hex digits
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))

        # Either safe char, or escape sequence
        string_char = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Build string content with length 0..20 to keep size bounded
        content = st.lists(string_char, max_size=20).map(''.join)
        return content.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # NUMBER strategy: generate valid JSON numbers as strings
    # Use Hypothesis floats converted to JSON number strings with bounded size
    def json_number():
        # Generate floats with limited exponent and decimal places
        # Also generate integers as strings
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        frac_part = st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)
            .map(lambda f: f"{f:.6f}".lstrip("0"))
        )
        exp_part = st.one_of(
            st.just(""),
            st.integers(min_value=-10, max_value=10).map(lambda e: f"e{e}")
        )

        # Compose number string carefully
        def compose_number():
            sign = st.one_of(st.just(""), st.just("-"))
            intp = int_part
            frac = st.one_of(st.just(""), st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)
                             .map(lambda f: f"{f:.6f}".split('.')[1].rstrip('0')))
            exp = exp_part
            # To keep it simpler, just generate floats and format them
            return st.floats(min_value=-1e6, max_value=1e6, allow_infinity=False, allow_nan=False).map(
                lambda f: format(f, '.6g')
            )
        return compose_number()

    json_number_st = json_number()

    # Forward declaration for recursive structures
    # We'll define value recursively with bounded depth
    # Use st.recursive to build obj and arr

    # Pair: STRING ':' value
    @st.composite
    def pair(draw):
        k = draw(json_string_st)
        v = draw(value)
        return f"{k}:{v}"

    # Object: '{' pair (',' pair)* '}' or '{}'
    def json_object():
        # Up to 3 pairs to keep size bounded
        pairs = st.lists(pair(), max_size=3)
        return pairs.map(lambda ps: "{" + ",".join(ps) + "}" if ps else "{}")

    # Array: '[' value (',' value)* ']' or '[]'
    def json_array():
        # Up to 3 elements to keep size bounded
        elems = st.lists(value, max_size=3)
        return elems.map(lambda vs: "[" + ",".join(vs) + "]" if vs else "[]")

    # Define value recursively
    # Base: string, number, true, false, null
    # Recursive: object, array
    base = st.one_of(
        json_string_st,
        json_number_st,
        json_true,
        json_false,
        json_null,
    )

    value = st.deferred(lambda: st.recursive(
        base,
        lambda children: st.one_of(
            json_object(),
            json_array(),
        ),
        max_leaves=10,
    ))

    # Compose full json: value + EOF (implicit)
    json_str = value

    s = draw(json_str)
    return s.encode("utf-8")