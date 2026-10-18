from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: simplified safe string with escapes
    def json_string():
        # Characters allowed inside strings (excluding control chars and " \)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)
        )
        # Escape sequences
        escape_seq = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t'
        ])
        # Unicode escape: \uXXXX
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))

        # Mix safe chars and escapes
        string_char = st.one_of(
            safe_char.map(lambda c: c),
            escape_seq,
            unicode_escape
        )
        # Build string content with length 0 to 20
        content = st.lists(string_char, max_size=20).map(''.join)
        return content.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # NUMBER strategy: use Hypothesis built-in floats and ints, then format as JSON number
    def json_number():
        # Generate int or float in JSON number format
        # Limit magnitude to keep size reasonable
        # Use floats with finite decimal representation or ints
        # We'll generate floats with limited decimal places
        int_part = st.integers(min_value=-10**6, max_value=10**6)
        frac_part = st.floats(
            min_value=-10**6, max_value=10**6,
            allow_infinity=False, allow_nan=False
        )
        # Choose int or float
        number = st.one_of(
            int_part.map(str),
            frac_part.map(lambda f: format(f, '.6g'))
        )
        return number

    json_number_st = json_number()

    # Recursive value strategy
    def json_value():
        # Forward declaration for recursion
        return st.deferred(lambda: value_st)

    # Object: { pair (, pair)* } or {}
    def json_object():
        # pair: STRING : value
        pair = st.tuples(json_string_st, json_value()).map(lambda t: f"{t[0]}:{t[1]}")
        # list of pairs, max 5 pairs to keep size bounded
        pairs = st.lists(pair, max_size=5)
        obj = pairs.map(lambda ps: "{" + ",".join(ps) + "}" if ps else "{}")
        return obj

    # Array: [ value (, value)* ] or []
    def json_array():
        values = st.lists(json_value(), max_size=5)
        arr = values.map(lambda vs: "[" + ",".join(vs) + "]" if vs else "[]")
        return arr

    # Compose value strategy with recursion bounded by max_leaves
    value_st = st.recursive(
        st.one_of(
            json_string_st,
            json_number_st,
            json_true,
            json_false,
            json_null,
        ),
        lambda children: st.one_of(
            json_object(),
            json_array(),
        ),
        max_leaves=10,
    )

    # Draw a value and append EOF (nothing) to produce full JSON text
    result = draw(value_st)
    return result.encode("utf-8")