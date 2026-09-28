from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # SAFECODEPOINT: any unicode char except control chars and " or \
    # We'll limit to BMP and exclude control chars and " and \
    def json_string():
        # Characters allowed inside strings (excluding control chars, " and \)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0xFFFF,
        )
        # Escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        # We'll produce either safe chars or escapes
        def escape():
            simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
            # Unicode escape: \uXXXX with hex digits
            hex_digit = st.sampled_from('0123456789abcdefABCDEF')
            unicode_escape = st.tuples(
                st.just('\\u'),
                hex_digit, hex_digit, hex_digit, hex_digit
            ).map(lambda t: ''.join(t))
            return st.one_of(simple_escapes, unicode_escape)

        # Compose string content as list of chars or escapes
        content = st.lists(st.one_of(safe_chars.map(lambda c: c), escape()), max_size=20)
        return content.map(lambda chars: '"' + ''.join(chars) + '"')

    json_string_st = json_string()

    # NUMBER strategy: produce valid JSON numbers
    # We'll use Hypothesis floats converted to JSON number strings, but restrict to finite numbers
    def json_number():
        # Generate numbers as strings matching JSON number grammar
        # We'll generate int or float strings manually to avoid scientific notation with 'p' etc.
        def number_str():
            # sign
            sign = st.one_of(st.just(''), st.just('-'))
            # int part
            int_part = st.one_of(
                st.just('0'),
                st.integers(min_value=1, max_value=10**6).map(str)
            )
            # fraction part
            fraction = st.one_of(st.just(''), st.floats(min_value=0, max_value=1).map(lambda f: f"{f:.6f}".lstrip('0')))
            # exponent part
            exponent = st.one_of(
                st.just(''),
                st.tuples(
                    st.sampled_from(['e', 'E']),
                    st.one_of(st.just(''), st.sampled_from(['+', '-'])),
                    st.integers(min_value=0, max_value=99).map(lambda x: f"{x}")
                ).map(lambda t: t[0] + t[1] + t[2])
            )
            return st.tuples(sign, int_part, fraction, exponent).map(lambda t: ''.join(t))

        # We'll filter out invalid fraction strings (empty or just '.')
        # Instead, build fraction as either empty or '.' + digits
        def number_str_fixed():
            sign = st.one_of(st.just(''), st.just('-'))
            int_part = st.one_of(
                st.just('0'),
                st.integers(min_value=1, max_value=10**6).map(str)
            )
            fraction = st.one_of(
                st.just(''),
                st.integers(min_value=0, max_value=999999).map(lambda x: '.' + f"{x:06d}".rstrip('0'))
            )
            exponent = st.one_of(
                st.just(''),
                st.tuples(
                    st.sampled_from(['e', 'E']),
                    st.one_of(st.just(''), st.sampled_from(['+', '-'])),
                    st.integers(min_value=0, max_value=99).map(lambda x: f"{x}")
                ).map(lambda t: t[0] + t[1] + t[2])
            )
            return st.tuples(sign, int_part, fraction, exponent).map(lambda t: ''.join(t))

        return number_str_fixed()

    json_number_st = json_number()

    # Recursive JSON value strategy
    # We'll limit recursion depth and size to keep output bounded
    # Compose value: string, number, obj, arr, true, false, null
    def json_value():
        # Forward declaration for recursion
        return st.recursive(
            base=st.one_of(
                json_string_st,
                json_number_st,
                json_true,
                json_false,
                json_null,
            ),
            extend=lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.builds(
                    lambda pairs: '{' + ','.join(pairs) + '}',
                    st.lists(
                        st.tuples(json_string_st, children).map(lambda t: t[0] + ':' + t[1]),
                        max_size=3
                    )
                ),
                # array: [ value (, value)* ] or []
                st.builds(
                    lambda values: '[' + ','.join(values) + ']',
                    st.lists(children, max_size=3)
                ),
            ),
            max_leaves=10,
        )

    val = draw(json_value())
    return val.encode('utf-8')