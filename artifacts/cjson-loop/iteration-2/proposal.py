from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string with safe codepoints and escapes
    # We include some escapes to keep near-valid cases
    def json_string():
        # SAFECODEPOINT ~["\\\u0000-\u001F], roughly printable except backslash and control chars
        safe_chars = st.characters(
            blacklist_characters=['\\', '"'] + [chr(c) for c in range(0x00, 0x20)]
        )
        # Escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape \uXXXX with hex digits
        hex_digit = st.sampled_from("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))
        escape = st.one_of(simple_escapes, unicode_escape)

        # Build string content: mix of safe chars and escapes
        # To keep near-valid, allow some escapes
        content = st.lists(st.one_of(safe_chars, escape), min_size=0, max_size=20).map(''.join)
        return content.map(lambda s: f'"{s}"')

    # JSON number
    # Use Hypothesis built-in floats but convert to JSON number string format
    def json_number():
        # Generate numbers that fit JSON number grammar
        # We'll generate floats and ints, then convert to string
        # Limit exponent range to keep sizes reasonable
        def to_json_number(n):
            # Format float to JSON number string without trailing .0 if int
            if isinstance(n, int):
                return str(n)
            else:
                # Use repr to get a compact representation
                s = repr(n)
                # JSON allows exponent, keep it as is
                return s
        # Generate int or float in reasonable range
        num = st.one_of(
            st.integers(min_value=-10**6, max_value=10**6),
            st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
        )
        return num.map(to_json_number)

    # Recursive JSON value strategy
    # Use bounded recursion to keep sizes manageable
    def json_value():
        base = st.one_of(
            json_string(),
            json_number(),
            json_true,
            json_false,
            json_null,
        )
        # Recursive containers: object and array
        # Use st.recursive with max_depth=3 to keep bounded
        return st.recursive(
            base,
            lambda children: st.one_of(
                # Object: { pair (, pair)* } or empty {}
                st.dictionaries(
                    keys=json_string(),
                    values=children,
                    min_size=0,
                    max_size=5,
                ).map(lambda d: (
                    '{' + ','.join(f'{k}:{v}' for k, v in d.items()) + '}'
                    if d else '{}'
                )),
                # Array: [ value (, value)* ] or empty []
                st.lists(children, min_size=0, max_size=5).map(lambda l: (
                    '[' + ','.join(l) + ']' if l else '[]'
                )),
            ),
            max_leaves=50,
        )

    # Compose full JSON text with EOF
    json_text = json_value()

    s = draw(json_text)
    return s.encode('utf-8')