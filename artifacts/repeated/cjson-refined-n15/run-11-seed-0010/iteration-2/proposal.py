from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode them as JSON strings.
    # To keep it simple and valid, use st.text with safe characters and escape quotes/backslashes.
    def json_string():
        # safe codepoints exclude control chars and quotes/backslash
        safe_chars = (
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # Compose string with length up to 20 to keep size bounded
        s = st.text(safe_chars, min_size=0, max_size=20)
        # Escape backslash and quotes in output
        def to_json_string(x: str) -> str:
            # Escape backslash and quotes and control chars per JSON spec
            # Also escape control chars \b \f \n \r \t
            def esc_char(c):
                if c == '"':
                    return '\\"'
                elif c == '\\':
                    return '\\\\'
                elif c == '\b':
                    return '\\b'
                elif c == '\f':
                    return '\\f'
                elif c == '\n':
                    return '\\n'
                elif c == '\r':
                    return '\\r'
                elif c == '\t':
                    return '\\t'
                elif ord(c) < 0x20:
                    # Unicode escape for control chars
                    return '\\u%04x' % ord(c)
                else:
                    return c
            return '"' + ''.join(esc_char(c) for c in x) + '"'
        return s.map(to_json_string)

    json_string_st = json_string()

    # NUMBER strategy: produce valid JSON numbers as strings
    # We'll generate floats and ints and convert to JSON number strings
    def json_number():
        # Use floats and ints, limit magnitude to keep size bounded
        # Also include negative numbers and exponents
        # Use floats with limited decimal places and exponents
        int_part = st.integers(min_value=-10**6, max_value=10**6)
        frac_part = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
        # Compose number strings with optional fractional and exponent parts
        def to_json_number(x):
            # Format float or int as JSON number string
            if isinstance(x, int):
                return str(x)
            else:
                # Format float with minimal representation
                s = format(x, '.15g')
                # JSON allows leading minus, digits, optional decimal point, optional exponent
                return s
        # Mix ints and floats
        return st.one_of(
            int_part.map(to_json_number),
            frac_part.map(to_json_number),
        )

    json_number_st = json_number()

    # Recursive JSON value strategy
    # Use st.recursive to build nested objects and arrays with bounded depth and size
    base = st.one_of(
        json_string_st,
        json_number_st,
        json_null,
        json_true,
        json_false,
    )

    # Forward declarations for obj and arr
    # pair: STRING ':' value
    # obj: '{' pair (',' pair)* '}' or '{}'
    # arr: '[' value (',' value)* ']' or '[]'

    # We'll define a helper to build pairs and objects
    def json_pair(value_st):
        # pair: STRING ':' value
        return st.tuples(json_string_st, value_st).map(lambda p: p[0] + ':' + p[1])

    def json_obj(value_st):
        # empty object or object with 1-5 pairs
        pairs = st.lists(json_pair(value_st), min_size=0, max_size=5)
        return pairs.map(lambda ps: '{' + (','.join(ps)) + '}')

    def json_arr(value_st):
        # empty array or array with 1-5 values
        vals = st.lists(value_st, min_size=0, max_size=5)
        return vals.map(lambda vs: '[' + (','.join(vs)) + ']')

    # Recursive strategy for value
    def json_value():
        return st.recursive(
            base,
            lambda children: st.one_of(
                json_obj(children),
                json_arr(children),
            ),
            max_leaves=20,
        )

    value_st = json_value()

    # Compose full JSON text: value + EOF
    json_text = value_st

    s = draw(json_text)
    return s.encode('utf-8')