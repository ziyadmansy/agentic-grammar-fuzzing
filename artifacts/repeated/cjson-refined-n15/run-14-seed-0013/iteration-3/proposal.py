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
        # Escapes: \" \\ \/ \b \f \n \r \t and unicode \uXXXX
        simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \u followed by 4 hex digits
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))

        # Either safe char or escape sequence
        char = st.one_of(
            safe_char.map(lambda c: c),
            simple_escapes,
            unicode_escape
        )
        # Build string content with length bounded to keep size reasonable
        content = st.lists(char, min_size=0, max_size=20).map(''.join)
        return content.map(lambda s: f'"{s}"')

    # NUMBER strategy: produce valid JSON numbers
    def json_number():
        # Use Hypothesis floats converted to JSON number strings
        # But restrict to finite numbers and reasonable range to avoid huge exponents
        # We'll build numbers manually to match grammar:
        # NUMBER : '-'? INT ('.' [0-9]+)? EXP? ;
        # INT : '0' | [1-9][0-9]* ;
        # EXP : [Ee][+-]?[0-9]+ ;
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        frac_part = st.one_of(
            st.none(),
            st.text(min_size=1, max_size=6, alphabet=st.characters(min_codepoint=48, max_codepoint=57))  # digits
        )
        exp_part = st.one_of(
            st.none(),
            st.tuples(
                st.sampled_from(['E', 'e']),
                st.sampled_from(['+', '-', '']),
                st.integers(min_value=0, max_value=99).map(lambda x: str(x))
            ).map(lambda t: t[0] + t[1] + t[2])
        )
        sign = st.one_of(st.just(''), st.just('-'))

        def build_number(t):
            s = t[0]
            if t[1] is not None:
                s += '.' + t[1]
            if t[2] is not None:
                s += t[2]
            return t[3] + s

        return st.tuples(int_part, frac_part, exp_part, sign).map(build_number)

    # Recursive JSON value strategy
    # Use st.recursive to build nested arrays and objects with bounded depth and size
    base = st.one_of(
        json_string(),
        json_number(),
        json_true,
        json_false,
        json_null,
    )

    # Forward declarations for recursive use
    @st.composite
    def json_value(draw):
        # Use recursive strategy with max depth 3 to keep sizes bounded
        def extend(value_strat):
            # Array: '[' value (',' value)* ']' or '[]'
            arr = st.lists(value_strat, min_size=0, max_size=4).map(
                lambda vs: '[' + ','.join(vs) + ']'
            )
            # Object: '{' pair (',' pair)* '}' or '{}'
            # pair: STRING ':' value
            pair = st.tuples(json_string(), value_strat).map(lambda p: f'{p[0]}:{p[1]}')
            obj = st.lists(pair, min_size=0, max_size=4).map(
                lambda ps: '{' + ','.join(ps) + '}'
            )
            return st.one_of(arr, obj)

        return draw(st.recursive(base, extend, max_leaves=10))

    # Compose full JSON text: value + EOF (EOF implicit by full string)
    json_text = json_value()

    s = draw(json_text)
    return s.encode('utf-8')