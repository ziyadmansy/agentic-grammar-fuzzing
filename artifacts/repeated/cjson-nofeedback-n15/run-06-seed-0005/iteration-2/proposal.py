from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escaped characters
        escape_seq = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape sequences
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.builds(
            lambda h1, h2, h3, h4: "\\u" + h1 + h2 + h3 + h4,
            hex_digit, hex_digit, hex_digit, hex_digit
        )
        # Either safe char, escape sequence, or unicode escape
        string_char = st.one_of(
            safe_char.map(lambda c: c),
            escape_seq,
            unicode_escape,
        )
        # Build a string of length 0..20 (bounded)
        content = st.text(string_char, min_size=0, max_size=20)
        return content.map(lambda s: '"' + s + '"')

    json_string_st = json_string()

    # NUMBER strategy: use Hypothesis floats converted to JSON number strings
    # but restrict to finite numbers and reasonable ranges
    def json_number():
        # Generate floats that can be represented as JSON numbers
        # Use decimals to avoid scientific notation sometimes
        # We'll generate strings matching the grammar
        # Use floats but convert to string with repr, then filter out inf/nan
        def float_to_json_number(f):
            # Format float to JSON number string
            # Use repr to get scientific notation if needed
            if f != f or f == float('inf') or f == float('-inf'):
                # Reject NaN and infinities
                raise st.InvalidArgument()
            s = repr(f)
            # repr can produce 'inf', 'nan', or scientific notation
            # JSON allows scientific notation, so keep as is
            return s

        return st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e10,
            max_value=1e10,
        ).map(float_to_json_number)

    json_number_st = json_number()

    # Forward declaration for recursive value
    # We'll define value recursively below

    # Recursive JSON value strategy
    # Use st.recursive to build nested arrays and objects

    # Base values: string, number, true, false, null
    base = st.one_of(
        json_string_st,
        json_number_st,
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: arrays and objects
    # Arrays: [ value (, value)* ] or []
    # Objects: { pair (, pair)* } or {}

    # pair: STRING : value
    def json_pair():
        return st.tuples(json_string_st, value).map(lambda p: p[0] + ":" + p[1])

    # We'll define value after this function to avoid forward reference issues
    # So we define a placeholder here and assign later
    value = st.deferred(lambda: value)

    # Arrays: either empty or non-empty list of values
    json_array = st.lists(value, min_size=0, max_size=5).map(
        lambda vs: "[" + ",".join(vs) + "]"
    )

    # Objects: either empty or non-empty list of pairs
    json_object = st.lists(json_pair(), min_size=0, max_size=5).map(
        lambda ps: "{" + ",".join(ps) + "}"
    )

    # Now define value as recursive combination
    value = st.recursive(
        base,
        lambda children: st.one_of(json_array, json_object),
        max_leaves=10,
    )

    # Compose full JSON with EOF (just ensure full consumption)
    json_full = value.map(lambda s: s)

    s = draw(json_full)
    return s.encode("utf-8")