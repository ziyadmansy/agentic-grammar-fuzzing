from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and " \)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escape sequences
        escape_seq = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape sequences
        hex_digit = st.sampled_from("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))

        # Mix safe chars and escapes
        char_piece = st.one_of(
            safe_char.map(lambda c: c),
            escape_seq,
            unicode_escape,
        )

        # Build string content with length limit
        content = st.text(char_piece, min_size=0, max_size=20)
        return content.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # NUMBER strategy: produce valid JSON numbers as strings
    def json_number():
        # Use Hypothesis floats but convert to JSON number string format
        # Limit floats to finite, avoid inf/nan
        # Also produce integers
        int_str = st.integers(min_value=-10**6, max_value=10**6).map(str)
        float_str = st.floats(
            allow_infinity=False,
            allow_nan=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ).map(lambda f: format(f, '.6g'))
        return st.one_of(int_str, float_str)

    json_number_st = json_number()

    # Recursive JSON value strategy
    # Use bounded recursion to avoid huge structures
    def json_value():
        # Base: primitives
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_null,
            json_true,
            json_false,
        )

        # Recursive containers
        # obj: {"pair", ...} or {}
        # pair: STRING : value
        # arr: [value, ...] or []

        # pair strategy
        pair_st = st.tuples(json_string_st, st.deferred(json_value)).map(
            lambda p: f'{p[0]}:{p[1]}'
        )

        # object strategy
        obj_st = st.one_of(
            st.just("{}"),
            st.lists(pair_st, min_size=1, max_size=5).map(
                lambda pairs: "{" + ",".join(pairs) + "}"
            ),
        )

        # array strategy
        arr_st = st.one_of(
            st.just("[]"),
            st.lists(st.deferred(json_value), min_size=1, max_size=5).map(
                lambda vals: "[" + ",".join(vals) + "]"
            ),
        )

        return st.one_of(base, obj_st, arr_st)

    # Compose full JSON document with EOF
    json_doc = json_value().map(lambda s: s)

    s = draw(json_doc)
    return s.encode("utf-8")