from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives as strings
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: produce valid JSON strings with escapes and safe codepoints
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escaped sequences
        escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape sequences
        hex_digit = st.characters('0123456789abcdefABCDEF')
        unicode_escape = st.builds(
            lambda h1, h2, h3, h4: '\\u' + h1 + h2 + h3 + h4,
            hex_digit, hex_digit, hex_digit, hex_digit
        )
        # Either safe char or escape sequence
        char = st.one_of(safe_char.map(lambda c: c), escapes, unicode_escape)
        # Compose string content with length limit to keep size bounded
        content = st.text(char, min_size=0, max_size=20)
        return content.map(lambda s: '"' + s + '"')

    # NUMBER: produce valid JSON numbers as strings
    def json_number():
        # Use Hypothesis floats converted to JSON number strings
        # Limit exponent and decimal places to keep size bounded
        def float_to_json_number(f):
            # Format float to JSON number string without trailing zeros
            if f == float('inf') or f == float('-inf') or f != f:
                # NaN or inf not valid JSON numbers, fallback to 0
                return "0"
            s = format(f, '.10g')
            # Remove trailing '.' if any
            if s.endswith('.'):
                s = s[:-1]
            return s
        return st.floats(
            allow_infinity=False,
            allow_nan=False,
            width=32,
            min_value=-1e10,
            max_value=1e10,
        ).map(float_to_json_number)

    # Recursive strategy for JSON values
    def json_value():
        # Base cases: string, number, true, false, null
        base = st.one_of(
            json_string(),
            json_number(),
            json_true,
            json_false,
            json_null,
        )

        # Recursive cases: object and array
        # Use st.recursive to keep recursion bounded
        return st.recursive(
            base,
            lambda children: st.one_of(
                # Object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string(),
                    values=children,
                    min_size=0,
                    max_size=4,
                ).map(lambda d: (
                    '{' + ','.join(f'{k}:{v}' for k, v in d.items()) + '}'
                )),
                # Array: [ value (, value)* ] or []
                st.lists(
                    children,
                    min_size=0,
                    max_size=4,
                ).map(lambda l: '[' + ','.join(l) + ']'),
            ),
            max_leaves=10,
        )

    # Draw a JSON value string
    json_str = draw(json_value())

    # Return as bytes
    return json_str.encode('utf-8')