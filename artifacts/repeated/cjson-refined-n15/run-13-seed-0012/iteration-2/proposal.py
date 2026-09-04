from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy matching grammar: '"' (ESC | SAFECODEPOINT)* '"'
    # SAFECODEPOINT: any char except " \ and control chars (U+0000-U+001F)
    # ESC: \ followed by one of ["\/bfnrt] or \uXXXX
    # We'll generate strings with safe unicode codepoints and some escapes.
    def json_string():
        # Characters allowed unescaped inside strings:
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escaped sequences:
        simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \uXXXX with hex digits
        hex_digit = st.sampled_from('0123456789abcdefABCDEF')
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))
        # Mix safe chars and escapes
        char_piece = st.one_of(
            safe_chars.map(lambda c: c),
            simple_escapes,
            unicode_escape
        )
        # Generate a list of 0 to 20 such pieces (bounded size)
        pieces = st.lists(char_piece, max_size=20)
        return pieces.map(lambda chars: '"' + ''.join(chars) + '"')

    json_string_st = json_string()

    # NUMBER: '-'? INT ('.' [0-9]+)? EXP?
    # INT: '0' | [1-9][0-9]*
    # EXP: [Ee][+-]?[0-9]+
    def json_number():
        # INT part
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        # Fractional part
        frac_part = st.one_of(
            st.just(""),
            st.builds(lambda dot, digits: dot + digits,
                      st.just('.'),
                      st.text(min_size=1, max_size=6, alphabet='0123456789'))
        )
        # Exponent part
        exp_part = st.one_of(
            st.just(""),
            st.builds(lambda e, sign, digits: e + sign + digits,
                      st.sampled_from(['E', 'e']),
                      st.one_of(st.just(''), st.sampled_from(['+', '-'])),
                      st.text(min_size=1, max_size=4, alphabet='0123456789'))
        )
        # Optional minus
        sign = st.one_of(st.just(''), st.just('-'))
        return st.builds(lambda s, i, f, e: s + i + f + e, sign, int_part, frac_part, exp_part)

    json_number_st = json_number()

    # Forward declare value for recursion
    # We'll use st.recursive to build obj and arr

    # Placeholder for value, will be replaced by recursive
    # We define value as a strategy returning a string representing JSON text

    def json_value():
        # Compose value from primitives and recursive containers
        # We'll define containers below and pass them here
        return st.deferred(lambda: value_st)

    # Object: '{' pair (',' pair)* '}' | '{}'
    # pair: STRING ':' value
    @st.composite
    def json_pair(draw):
        k = draw(json_string_st)
        v = draw(json_value())
        return f"{k}:{v}"

    @st.composite
    def json_obj(draw):
        # empty or pairs
        # limit number of pairs to keep size bounded
        pairs = draw(st.lists(json_pair(), max_size=5))
        if not pairs:
            return "{}"
        else:
            return "{" + ",".join(pairs) + "}"

    # Array: '[' value (',' value)* ']' | '[]'
    @st.composite
    def json_arr(draw):
        vals = draw(st.lists(json_value(), max_size=5))
        if not vals:
            return "[]"
        else:
            return "[" + ",".join(vals) + "]"

    # Compose value strategy with recursion
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

    # Compose full json: value EOF
    json_text = draw(value_st)
    # Return bytes
    return json_text.encode("utf-8")