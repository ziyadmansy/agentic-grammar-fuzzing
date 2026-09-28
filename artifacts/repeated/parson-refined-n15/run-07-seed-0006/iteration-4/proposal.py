from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: produce valid JSON strings with safe codepoints and escapes
    # SAFECODEPOINT ~["\\\u0000-\u001F], so exclude control chars and backslash and quote
    # We'll allow common escapes as well.
    # Use st.text with a safe alphabet plus escapes.
    # To keep near-valid, sometimes produce invalid escapes or unescaped control chars.
    def json_string():
        # safe chars excluding " and \ and control chars
        safe_chars = (
            [chr(c) for c in range(0x20, 0x7F) if chr(c) not in ['"', '\\']]
            + ['\u20AC', '\u00A9', '\u03A9']  # some unicode chars
        )
        # 80% valid strings, 20% near-valid with some invalid escapes or control chars
        valid_str = st.text(safe_chars, min_size=0, max_size=20)
        # invalid string: include some control chars or unescaped quotes or backslashes
        invalid_chars = [chr(c) for c in range(0x00, 0x20)] + ['"', '\\']
        invalid_str = st.text(invalid_chars, min_size=1, max_size=5)
        use_valid = draw(st.booleans())
        s = draw(valid_str if use_valid else invalid_str)
        # encode escapes for valid strings
        if use_valid:
            # replace some chars with escapes randomly
            def escape_char(c):
                if c == '"':
                    return '\\"'
                if c == '\\':
                    return '\\\\'
                if c == '\b':
                    return '\\b'
                if c == '\f':
                    return '\\f'
                if c == '\n':
                    return '\\n'
                if c == '\r':
                    return '\\r'
                if c == '\t':
                    return '\\t'
                # for other control chars, use unicode escape
                if ord(c) < 0x20:
                    return '\\u%04x' % ord(c)
                return c
            # randomly escape some chars
            escaped_chars = []
            for c in s:
                if draw(st.booleans()):
                    escaped_chars.append(escape_char(c))
                else:
                    escaped_chars.append(c)
            s = "".join(escaped_chars)
        # wrap in quotes
        return '"' + s + '"'

    json_string_st = st.deferred(json_string)

    # NUMBER: produce valid JSON numbers, sometimes near-valid (e.g. leading zeros)
    def json_number():
        # 80% valid, 20% near-valid
        valid_number = st.one_of(
            st.integers(min_value=-(10**9), max_value=10**9).map(str),
            st.floats(allow_infinity=False, allow_nan=False, width=32).map(lambda f: format(f, 'g')),
            st.decimals(allow_nan=False, allow_infinity=False).map(lambda d: format(d, 'f').rstrip('0').rstrip('.') if '.' in format(d, 'f') else format(d, 'f')),
        )
        # near-valid: leading zeros, trailing dots, missing digits after exponent
        near_valid = st.sampled_from([
            "00", "01", "-00", "1.", "1e", "1e+", "1e-", "-.1", ".", "-",
        ])
        use_valid = draw(st.booleans())
        return draw(valid_number if use_valid else near_valid)

    json_number_st = st.deferred(json_number)

    # Recursive JSON value strategy
    # To keep sizes bounded, limit max_depth
    max_depth = 4

    def json_value_strategy(depth=0):
        if depth >= max_depth:
            # only primitives at max depth
            return st.one_of(json_string_st, json_number_st, json_null, json_true, json_false)
        else:
            # recursively build arrays and objects
            array_st = st.lists(json_value_strategy(depth + 1), min_size=0, max_size=5).map(
                lambda vs: "[" + ",".join(vs) + "]"
            )
            # pairs: STRING : value
            pair_st = st.tuples(json_string_st, json_value_strategy(depth + 1)).map(
                lambda p: p[0] + ":" + p[1]
            )
            object_st = st.lists(pair_st, min_size=0, max_size=5).map(
                lambda pairs: "{" + ",".join(pairs) + "}"
            )
            return st.one_of(
                json_string_st,
                json_number_st,
                json_null,
                json_true,
                json_false,
                array_st,
                object_st,
            )

    # Compose full JSON text with EOF
    json_text = json_value_strategy()

    s = draw(json_text)
    return s.encode("utf-8")