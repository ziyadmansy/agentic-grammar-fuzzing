from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    def json_string():
        # Characters allowed inside strings (excluding control chars and " \)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\b', r'\f', r'\n', r'\r', r'\t',
        ])
        # Unicode escape \uXXXX with hex digits
        hex_digit = st.sampled_from("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: "".join(t))

        # Compose string content from safe chars and escapes
        string_char = st.one_of(
            safe_char.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Limit length to keep output bounded
        content = st.lists(string_char, max_size=20).map("".join)
        return content.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # NUMBER strategy: use Hypothesis built-in floats and ints, then format as JSON number
    def json_number():
        # Generate int or float within reasonable bounds
        # Use floats but exclude NaN and inf by default
        number = st.one_of(
            st.integers(min_value=-(10**9), max_value=10**9),
            st.floats(allow_nan=False, allow_infinity=False, width=32)
        )
        def to_json_number(n):
            # Format int as int, float as JSON number string
            if isinstance(n, int):
                return str(n)
            else:
                # Use repr to get a JSON-compatible float string
                s = repr(n)
                # Ensure decimal point or exponent present for floats
                if 'e' not in s and '.' not in s:
                    s += '.0'
                return s
        return number.map(to_json_number)

    json_number_st = json_number()

    # Recursive value strategy
    def json_value():
        # Forward declare to use recursion
        return st.deferred(lambda: value_st)

    # Pair: STRING ':' value
    @st.composite
    def json_pair(draw):
        k = draw(json_string_st)
        v = draw(json_value())
        return f"{k}:{v}"

    # Object: '{' pair (',' pair)* '}' or '{}'
    @st.composite
    def json_object(draw):
        # Limit number of pairs to keep size bounded
        pairs = draw(st.lists(json_pair(), max_size=3))
        if not pairs:
            return "{}"
        return "{" + ",".join(pairs) + "}"

    # Array: '[' value (',' value)* ']' or '[]'
    @st.composite
    def json_array(draw):
        values = draw(st.lists(json_value(), max_size=3))
        if not values:
            return "[]"
        return "[" + ",".join(values) + "]"

    # Compose the value strategy with recursion bounded
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

    # Compose full JSON text: value + EOF (implicit)
    json_text = value_st

    s = draw(json_text)
    return s.encode("utf-8")