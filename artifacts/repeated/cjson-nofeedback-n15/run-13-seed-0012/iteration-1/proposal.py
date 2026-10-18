from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    def json_string():
        # Characters allowed inside strings (excluding control chars and " \)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape \uXXXX
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))
        # Either a safe char or an escape sequence
        json_char = st.one_of(
            safe_char.map(lambda c: c),
            simple_escapes,
            unicode_escape
        )
        # Build string of length 0..20 (bounded)
        chars = st.lists(json_char, max_size=20)
        return chars.map(lambda cs: '"' + ''.join(cs) + '"')

    # NUMBER strategy: produce valid JSON numbers
    def json_number():
        # Use Hypothesis built-in floats but convert to JSON number string
        # We'll generate numbers as strings to avoid float formatting issues
        # Compose number parts manually
        sign = st.one_of(st.just(''), st.just('-'))
        int_part = st.one_of(st.just('0'), st.integers(min_value=1, max_value=10**6).map(str))
        frac_part = st.one_of(st.just(''), st.floats(min_value=0, max_value=1).map(lambda f: f"{f:.6f}".lstrip('0')))
        # frac_part above can produce e.g. ".123456"
        # But to be safe, build fractional part manually:
        def fraction():
            # Either empty or '.' + digits
            digits = st.text(st.characters(min_codepoint=48, max_codepoint=57), min_size=1, max_size=6)
            return st.one_of(st.just(''), digits.map(lambda d: '.' + d))
        frac_part = fraction()
        # exponent part
        def exponent():
            sign_exp = st.one_of(st.just(''), st.sampled_from(['+', '-']))
            digits_exp = st.text(st.characters(min_codepoint=48, max_codepoint=57), min_size=1, max_size=4)
            return st.one_of(st.just(''), st.tuples(st.sampled_from(['e', 'E']), sign_exp, digits_exp).map(lambda t: t[0] + t[1] + t[2]))
        exp_part = exponent()

        return st.tuples(sign, int_part, frac_part, exp_part).map(lambda t: ''.join(t))

    # Recursive JSON value strategy
    def json_value():
        # Forward declaration for recursion
        return st.deferred(lambda: json_value_inner())

    # Compose object and array with bounded recursion depth
    max_depth = 3

    def json_value_inner(depth=0):
        if depth >= max_depth:
            # At max depth, only primitives
            return st.one_of(
                json_string(),
                json_number(),
                json_null,
                json_true,
                json_false,
            )
        else:
            # Compose object, array, and primitives
            # Object: { pair (, pair)* } or {}
            # pair: STRING : value
            # Array: [ value (, value)* ] or []
            # Use bounded size lists for pairs and array elements
            pair = st.tuples(json_string(), json_value_inner(depth + 1)).map(lambda t: t[0] + ':' + t[1])
            obj = st.one_of(
                st.just('{}'),
                st.lists(pair, max_size=4).map(lambda pairs: '{' + ','.join(pairs) + '}')
            )
            arr = st.one_of(
                st.just('[]'),
                st.lists(json_value_inner(depth + 1), max_size=4).map(lambda vs: '[' + ','.join(vs) + ']')
            )
            return st.one_of(
                json_string(),
                json_number(),
                obj,
                arr,
                json_null,
                json_true,
                json_false,
            )

    # Compose full JSON text and encode as bytes
    json_text = json_value_inner()

    result = draw(json_text)
    return result.encode('utf-8')