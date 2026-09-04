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
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t'
        ])
        # Unicode escape: \uXXXX with hex digits
        hex_digit = st.sampled_from("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: "".join(t))

        # Build string content from a mix of safe chars and escapes
        # To keep near-valid cases, sometimes produce invalid escapes by mixing
        # but mostly valid escapes
        content_char = st.one_of(
            safe_char.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Generate a list of 0 to 20 content chars
        content = st.lists(content_char, max_size=20).map("".join)
        return content.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # NUMBER strategy: produce valid JSON numbers as strings
    def json_number():
        # Use Hypothesis built-in floats but convert to JSON number strings
        # Limit to finite numbers, no NaN or inf
        # Use decimal notation, sometimes with exponent
        def float_to_json_number(f):
            # Format float as JSON number string
            # Use repr to get a compact representation
            s = repr(f)
            # repr may produce inf/nan, filter them out by strategy
            if s in ('inf', '-inf', 'nan', '-nan'):
                return "0"
            # JSON numbers cannot have leading +, so repr is safe
            return s

        return st.floats(allow_infinity=False, allow_nan=False).map(float_to_json_number)

    json_number_st = json_number()

    # Recursive value strategy
    def json_value():
        # Forward declaration for recursion
        return st.deferred(lambda: value_st)

    # Pair: STRING : value
    @st.composite
    def pair(draw):
        k = draw(json_string_st)
        v = draw(json_value())
        return f"{k}:{v}"

    # Object: { pair (, pair)* } or {}
    @st.composite
    def obj(draw):
        # Limit number of pairs to keep size bounded
        pairs = draw(st.lists(pair(), max_size=5))
        if pairs:
            return "{" + ",".join(pairs) + "}"
        else:
            return "{}"

    # Array: [ value (, value)* ] or []
    @st.composite
    def arr(draw):
        values = draw(st.lists(json_value(), max_size=5))
        if values:
            return "[" + ",".join(values) + "]"
        else:
            return "[]"

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
            obj(),
            arr(),
        ),
        max_leaves=10,
    )

    # Compose full JSON: value + EOF (implicit)
    json_text = draw(value_st)
    return json_text.encode("utf-8")