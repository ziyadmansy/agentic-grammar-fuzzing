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
        # Escape sequences
        escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \uXXXX
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))

        # Mix safe chars and escapes/unicode escapes
        char_piece = st.one_of(
            safe_char.map(lambda c: c),
            escapes,
            unicode_escape,
        )

        # Generate a list of pieces for the string content
        pieces = st.lists(char_piece, min_size=0, max_size=20).map(''.join)
        return pieces.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # NUMBER strategy: mimic JSON number format
    json_number = st.builds(
        lambda neg, int_part, frac, exp: (
            ('-' if neg else '') +
            int_part +
            ('.' + frac if frac else '') +
            (exp if exp else '')
        ),
        neg=st.booleans(),
        int_part=st.one_of(
            st.just('0'),
            st.integers(min_value=1, max_value=10**6).map(str)
        ),
        frac=st.one_of(st.none(), st.text(min_size=1, max_size=6, alphabet=st.characters('0123456789'))),
        exp=st.one_of(
            st.none(),
            st.builds(
                lambda e, s, d: f"{e}{s}{d}",
                e=st.sampled_from(['e', 'E']),
                s=st.sampled_from(['+', '-', '']),
                d=st.text(min_size=1, max_size=3, alphabet=st.characters('0123456789'))
            )
        )
    )

    # Recursive JSON value strategy
    def json_value():
        # Forward declaration to allow recursion
        return st.deferred(lambda: json_value_inner())

    # Compose object and array with bounded recursion and size
    def json_object():
        # pair: STRING ':' value
        pair = st.tuples(json_string_st, json_value())
        # limit number of pairs to keep size bounded
        pairs = st.lists(pair, max_size=5)
        return pairs.map(
            lambda ps: '{' + ','.join(f'{k}:{v}' for k, v in ps) + '}' if ps else '{}'
        )

    def json_array():
        # list of values, max size 5
        values = st.lists(json_value(), max_size=5)
        return values.map(
            lambda vs: '[' + ','.join(vs) + ']' if vs else '[]'
        )

    def json_value_inner():
        return st.one_of(
            json_string_st,
            json_number,
            json_object(),
            json_array(),
            json_true,
            json_false,
            json_null,
        )

    # Draw a JSON value and encode as bytes
    s = draw(json_value())
    return s.encode('utf-8')