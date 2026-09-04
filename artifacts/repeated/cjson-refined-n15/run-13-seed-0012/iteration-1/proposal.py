from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, '.15g'))
    # JSON strings with safe codepoints and escapes
    # We'll allow some escapes to preserve near-valid cases
    # SAFECODEPOINT ~["\\\u0000-\u001F], roughly printable except backslash and control chars
    # We'll generate strings with a mix of safe chars and some escapes
    def json_string():
        # safe chars excluding control and backslash and quote
        safe_chars = st.characters(
            blacklist_characters=['\\', '"'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # escapes: \" \\ \/ \b \f \n \r \t and unicode \uXXXX
        simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # unicode escape \uXXXX
        hex_digit = st.sampled_from('0123456789abcdefABCDEF')
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))
        # mix safe chars and escapes
        char = st.one_of(
            safe_chars.map(lambda c: c),
            simple_escapes,
            unicode_escape,
        )
        # length bounded to keep size reasonable
        chars = st.lists(char, min_size=0, max_size=20).map(''.join)
        return chars.map(lambda s: f'"{s}"')

    json_string = json_string()

    # Recursive JSON values: string, number, obj, arr, true, false, null
    # Use st.recursive to bound size and depth
    def json_value():
        base = st.one_of(
            json_string,
            json_number,
            json_true,
            json_false,
            json_null,
        )
        # obj and arr will be defined recursively
        return st.recursive(
            base,
            lambda children: st.one_of(
                # obj: {} or {"pair", ...}
                st.builds(
                    lambda pairs: '{' + ','.join(pairs) + '}',
                    st.lists(
                        st.tuples(
                            json_string,
                            children,
                        ).map(lambda p: f'{p[0]}:{p[1]}'),
                        max_size=3,
                    ),
                ),
                # empty obj
                st.just('{}'),
                # arr: [] or [value, ...]
                st.builds(
                    lambda values: '[' + ','.join(values) + ']',
                    st.lists(children, max_size=3),
                ),
                # empty arr
                st.just('[]'),
            ),
            max_leaves=10,
        )

    json_val = json_value()

    # The top-level json is a value followed by EOF
    s = draw(json_val)
    return s.encode('utf-8')