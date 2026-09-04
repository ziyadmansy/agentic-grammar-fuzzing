from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll keep it simple: ASCII printable except control chars and backslash/quote,
    # plus some escapes.
    # Use a small max size to keep examples small.
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars, quote, backslash)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\b', r'\f', r'\n', r'\r', r'\t',
        ])
        # Unicode escape: \u + 4 hex digits
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: "".join(t))

        # Either a safe char or an escape sequence
        char_or_escape = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Compose string content of length 0..20
        content = st.lists(char_or_escape, max_size=20).map("".join)
        return content.map(lambda s: f'"{s}"')

    json_string_strat = json_string()

    # NUMBER strategy: use Hypothesis built-in floats converted to JSON number strings
    # but restrict to finite numbers and reasonable ranges to avoid huge exponents
    def json_number():
        # Generate floats excluding NaN and inf
        # Limit magnitude to avoid huge exponents
        f = st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e10,
            max_value=1e10,
        )
        # Convert float to JSON number string (no trailing .0 if int)
        def to_json_number(x):
            # Use repr to get a short float string
            s = repr(x)
            # repr may produce 'inf' or 'nan' but filtered above
            # Remove trailing .0 if integer
            if s.endswith(".0"):
                s = s[:-2]
            return s
        return f.map(to_json_number)

    json_number_strat = json_number()

    # Recursive JSON value strategy
    # Use st.recursive to build nested objects and arrays with bounded depth and size
    base = st.one_of(
        json_string_strat,
        json_number_strat,
        json_null,
        json_true,
        json_false,
    )

    # Forward declare value to use in obj and arr
    # We'll build obj and arr as strings directly
    def json_obj():
        # pair: STRING ':' value
        pair = st.tuples(json_string_strat, value).map(lambda t: f"{t[0]}:{t[1]}")
        # non-empty object: '{' pair (',' pair)* '}'
        non_empty_obj = st.lists(pair, min_size=1, max_size=5).map(
            lambda pairs: "{" + ",".join(pairs) + "}"
        )
        # empty object: '{}'
        empty_obj = st.just("{}")
        return st.one_of(non_empty_obj, empty_obj)

    def json_arr():
        # array: '[' value (',' value)* ']' or '[]'
        non_empty_arr = st.lists(value, min_size=1, max_size=5).map(
            lambda vals: "[" + ",".join(vals) + "]"
        )
        empty_arr = st.just("[]")
        return st.one_of(non_empty_arr, empty_arr)

    # Compose value recursively
    value = st.recursive(
        base,
        lambda children: st.one_of(
            json_obj(),
            json_arr(),
        ),
        max_leaves=10,
    )

    # Compose full JSON: value + EOF (no trailing data)
    json_text = value

    s = draw(json_text)
    return s.encode("utf-8")