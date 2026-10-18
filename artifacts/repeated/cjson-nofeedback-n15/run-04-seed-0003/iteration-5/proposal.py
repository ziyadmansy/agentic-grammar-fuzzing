from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # SAFECODEPOINT: any Unicode codepoint except control chars and " or \
    # We'll limit to BMP and exclude control chars and " and \
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars, " and \)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0xFFFF,
        )
        # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\b', r'\f', r'\n', r'\r', r'\t'
        ])
        # Unicode escape \uXXXX with hex digits
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

        # Compose string content with length 0..20 to keep size bounded
        content = st.lists(char_or_escape, max_size=20).map("".join)
        return content.map(lambda s: f'"{s}"')

    # NUMBER strategy: use Hypothesis floats and ints formatted as JSON numbers
    def json_number():
        # Generate numbers as strings matching the grammar
        # Use floats and ints, convert to JSON number strings
        # Limit floats to finite values, no inf/nan
        number = st.one_of(
            st.integers(min_value=-10**6, max_value=10**6).map(str),
            st.floats(
                allow_infinity=False,
                allow_nan=False,
                width=32,
                min_value=-1e6,
                max_value=1e6,
            ).map(lambda f: format(f, '.6g'))
        )
        return number

    # Recursive value strategy
    # value = STRING | NUMBER | obj | arr | true | false | null
    # Use st.recursive to build obj and arr

    # Forward declare value to use in obj and arr
    # We'll define value as a recursive strategy below

    # Pair: STRING ':' value
    @st.composite
    def pair(draw, value):
        key = draw(json_string())
        val = draw(value)
        return f"{key}:{val}"

    # Object: '{' pair (',' pair)* '}' or '{}'
    def json_object(value):
        # 0 to 5 pairs to keep size bounded
        pairs = st.lists(pair(value), max_size=5)
        return pairs.map(
            lambda ps: "{" + ",".join(ps) + "}" if ps else "{}"
        )

    # Array: '[' value (',' value)* ']' or '[]'
    def json_array(value):
        values = st.lists(value, max_size=5)
        return values.map(
            lambda vs: "[" + ",".join(vs) + "]" if vs else "[]"
        )

    # Define value recursively
    value = st.recursive(
        base=st.one_of(
            json_string(),
            json_number(),
            json_true,
            json_false,
            json_null,
        ),
        extend=lambda children: st.one_of(
            json_object(children),
            json_array(children),
        ),
        max_leaves=10,
    )

    # Compose full JSON: value + EOF (implicit)
    json_text = value

    s = draw(json_text)
    return s.encode("utf-8")