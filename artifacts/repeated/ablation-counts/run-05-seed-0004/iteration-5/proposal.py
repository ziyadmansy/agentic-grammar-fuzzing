from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives as strings
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy producing valid JSON strings with escapes
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and " \)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)
        )
        # Escapes
        escapes = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t'
        ])
        # Unicode escape: \uXXXX
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))

        # Either a safe char, or an escape sequence
        json_char = st.one_of(
            safe_char.map(lambda c: c),
            escapes,
            unicode_escape,
        )

        # Compose string content with length limit to keep size bounded
        content = st.text(json_char, min_size=0, max_size=20)
        return content.map(lambda s: '"' + s + '"')

    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, '.15g'))
    # But floats can produce scientific notation, which is valid JSON number.
    # To avoid negative zero "-0", we convert -0.0 to 0.0
    def fix_number(s):
        if s == '-0':
            return '0'
        return s
    json_number = json_number.map(fix_number)

    # Recursive JSON value strategy
    # We'll define a helper function to build recursive JSON values as strings
    def json_value():
        # Forward declaration for recursion
        return st.deferred(lambda: json_value_inner())

    # Object: { pair (, pair)* } or {}
    def json_object():
        # pair: STRING : value
        pair = st.tuples(json_string(), json_value()).map(lambda p: f'{p[0]}:{p[1]}')
        pairs = st.lists(pair, max_size=3)
        obj = pairs.map(lambda ps: '{' + (',' .join(ps) if ps else '') + '}')
        return obj

    # Array: [ value (, value)* ] or []
    def json_array():
        arr = st.lists(json_value(), max_size=3)
        return arr.map(lambda vs: '[' + (',' .join(vs) if vs else '') + ']')

    def json_value_inner():
        return st.one_of(
            json_string(),
            json_number,
            json_object(),
            json_array(),
            json_true,
            json_false,
            json_null,
        )

    # Compose full JSON text with EOF
    json_text = json_value().map(lambda s: s)

    s = draw(json_text)
    return s.encode('utf-8')