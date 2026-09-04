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
        # Escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \uXXXX
        hex_digit = st.characters(min_codepoint=0x30, max_codepoint=0x39).filter(lambda c: c in "0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just('\\u'),
            st.sampled_from('0123456789abcdefABCDEF'),
            st.sampled_from('0123456789abcdefABCDEF'),
            st.sampled_from('0123456789abcdefABCDEF'),
            st.sampled_from('0123456789abcdefABCDEF'),
        ).map(lambda t: ''.join(t))
        # Compose string content from safe chars, escapes, and unicode escapes
        string_char = st.one_of(
            safe_char.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Limit string length to keep size bounded
        content = st.lists(string_char, min_size=0, max_size=20).map(''.join)
        return content.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # NUMBER strategy: produce valid JSON numbers as strings
    def json_number():
        # Use Hypothesis built-in floats but convert to JSON number string format
        # Limit floats to finite, non-NaN, non-infinite
        # Use decimal notation or scientific notation
        def float_to_json_number(f):
            # Format float to JSON number string without trailing .0 if integer
            if f == int(f):
                return str(int(f))
            else:
                # Use repr to get scientific notation if needed
                return repr(f)
        return st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e10,
            max_value=1e10,
        ).map(float_to_json_number)

    json_number_st = json_number()

    # Recursive JSON value strategy
    # Use st.recursive to build nested objects and arrays with bounded depth and size
    def json_value():
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_null,
            json_true,
            json_false,
        )
        # Recursive containers
        def obj():
            # pair: STRING : value
            pair = st.tuples(json_string_st, json_value()).map(lambda p: f'{p[0]}:{p[1]}')
            # zero or more pairs separated by commas, bounded size
            pairs = st.lists(pair, max_size=5)
            return pairs.map(lambda ps: '{' + (','.join(ps)) + '}')

        def arr():
            # zero or more values separated by commas, bounded size
            values = st.lists(json_value(), max_size=5)
            return values.map(lambda vs: '[' + (','.join(vs)) + ']')

        return st.recursive(
            base,
            lambda children: st.one_of(obj(), arr()),
            max_leaves=10,
        )

    json_st = json_value()

    # Compose final JSON with EOF (no trailing data)
    json_str = draw(json_st)
    return json_str.encode('utf-8')