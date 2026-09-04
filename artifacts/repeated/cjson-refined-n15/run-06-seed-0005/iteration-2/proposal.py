from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and " \)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t'
        ])
        # Unicode escape \uXXXX
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: "".join(t))

        # Mix safe chars and escapes/unicode escapes
        # To keep near-valid cases, sometimes insert invalid escapes (e.g. incomplete)
        # but mostly valid escapes
        # We'll produce a list of length 0..20
        def string_char():
            # 80% safe char, 10% escape, 10% unicode escape
            choice = draw(st.integers(min_value=1, max_value=100))
            if choice <= 80:
                return draw(safe_chars)
            elif choice <= 90:
                return draw(escapes)
            else:
                return draw(unicode_escape)

        # Compose string content
        length = draw(st.integers(min_value=0, max_value=20))
        chars = [string_char() for _ in range(length)]
        content = "".join(chars)
        return f'"{content}"'

    json_string_st = st.builds(json_string)

    # NUMBER strategy: valid JSON numbers, plus near-valid (e.g. trailing dot)
    def json_number():
        # Use Hypothesis float strategy, then convert to JSON number string
        # But to keep near-valid, sometimes produce trailing dot or missing exponent digits
        base_float = st.floats(allow_infinity=False, allow_nan=False, width=32)
        f = draw(base_float)
        # Format float as JSON number string
        s = format(f, "g")
        # Possibly add trailing dot (near-valid)
        if draw(st.booleans()):
            if '.' in s and not s.endswith('.'):
                s += '.'
        # Possibly add incomplete exponent (e.g. "1e")
        if draw(st.booleans()):
            if 'e' not in s and 'E' not in s:
                s += 'e'
        return s

    json_number_st = st.deferred(json_number)

    # Forward declaration for recursive value
    # We'll use st.recursive to build obj and arr

    # Placeholder for value strategy, to be defined later
    value_st = st.deferred(lambda: value_st)

    # obj: '{' pair (',' pair)* '}' or '{}'
    # pair: STRING ':' value
    @st.composite
    def json_pair(draw):
        key = draw(json_string_st)
        val = draw(value_st)
        return f"{key}:{val}"

    @st.composite
    def json_obj(draw):
        # Empty or with pairs
        if draw(st.booleans()):
            # empty object
            return "{}"
        else:
            # 1 to 5 pairs
            n = draw(st.integers(min_value=1, max_value=5))
            pairs = [draw(json_pair()) for _ in range(n)]
            return "{" + ",".join(pairs) + "}"

    # arr: '[' value (',' value)* ']' or '[]'
    @st.composite
    def json_arr(draw):
        if draw(st.booleans()):
            return "[]"
        else:
            n = draw(st.integers(min_value=1, max_value=5))
            vals = [draw(value_st) for _ in range(n)]
            return "[" + ",".join(vals) + "]"

    # Define value strategy recursively
    value_st = st.recursive(
        st.one_of(
            json_string_st,
            json_number_st,
            json_null,
            json_true,
            json_false,
        ),
        lambda children: st.one_of(
            json_obj(),
            json_arr(),
        ),
        max_leaves=10,
    )

    # Draw a full JSON value and append EOF (implicit)
    result = draw(value_st)
    # Return as bytes
    return result.encode("utf-8")