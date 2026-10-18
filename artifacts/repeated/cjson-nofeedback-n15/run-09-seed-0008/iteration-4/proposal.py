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
        # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\b', r'\f', r'\n', r'\r', r'\t',
        ])
        # Unicode escape \uXXXX with hex digits
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))

        # Compose string content from safe chars and escapes
        # Mix safe chars and escapes, length bounded
        content_char = st.one_of(
            safe_char.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Limit length to keep output size bounded
        content = st.lists(content_char, max_size=20).map(''.join)
        return content.map(lambda s: f'"{s}"')

    # NUMBER strategy: produce valid JSON numbers
    def json_number():
        # Use Hypothesis built-in floats, then format to JSON number string
        # Limit to finite floats, no inf/nan
        # Also include integers
        def format_number(n):
            # Format float or int to JSON number string
            if isinstance(n, int):
                return str(n)
            else:
                # Use repr to get JSON-compatible float string
                s = repr(n)
                # JSON requires decimal point for floats
                if '.' not in s and 'e' not in s and 'E' not in s:
                    s += '.0'
                return s
        # Generate int or float in a reasonable range
        number = st.one_of(
            st.integers(min_value=-10**6, max_value=10**6),
            st.floats(
                min_value=-1e6, max_value=1e6,
                allow_infinity=False, allow_nan=False,
                width=32,
            )
        )
        return number.map(format_number)

    # Recursive strategy for JSON values
    def json_value():
        # Base: primitives
        base = st.one_of(
            json_string(),
            json_number(),
            json_null,
            json_true,
            json_false,
        )

        # Recursive containers: objects and arrays
        # Use bounded recursion depth and size
        return st.recursive(
            base,
            lambda children: st.one_of(
                # Object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string(),
                    values=children,
                    max_size=5,
                ).map(
                    lambda d: (
                        '{' + ','.join(f'{k}:{v}' for k, v in d.items()) + '}'
                        if d else '{}'
                    )
                ),
                # Array: [ value (, value)* ] or []
                st.lists(children, max_size=5).map(
                    lambda l: '[' + ','.join(l) + ']' if l else '[]'
                ),
            ),
            max_leaves=10,
        )

    s = json_value()
    result = draw(s)
    return result.encode('utf-8')