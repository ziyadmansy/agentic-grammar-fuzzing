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
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escape sequences
        escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape sequences
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))

        # Mix safe chars and escapes/unicode escapes
        # To keep it simple, generate a list of either safe chars or escapes
        char_piece = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Generate a list of such pieces, length bounded
        pieces = st.lists(char_piece, max_size=20)
        s = draw(pieces)
        # Join and wrap in quotes
        return '"' + ''.join(s) + '"'

    json_string_st = st.deferred(json_string)

    # NUMBER strategy: generate valid JSON numbers as strings
    def json_number():
        # Use Hypothesis built-in floats but convert to JSON number string format
        # We'll generate floats and ints as strings matching the grammar
        # To keep it simple, generate strings matching the NUMBER regex
        # We'll generate:
        # optional minus, integer part, optional fraction, optional exponent
        sign = st.one_of(st.just(''), st.just('-'))
        int_part = st.one_of(
            st.just('0'),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        frac_part = st.one_of(st.just(''), st.floats(min_value=0, max_value=1).map(lambda f: f"{f:.6f}"[1:]))
        # frac_part produces something like ".123456" or ""
        exp_part = st.one_of(
            st.just(''),
            st.tuples(
                st.sampled_from(['e', 'E']),
                st.one_of(st.just(''), st.sampled_from(['+', '-'])),
                st.integers(min_value=0, max_value=1000)
            ).map(lambda t: t[0] + t[1] + str(t[2]))
        )
        return st.tuples(sign, int_part, frac_part, exp_part).map(lambda t: ''.join(t))

    json_number_st = json_number()

    # Recursive definition for value
    # We use st.recursive to keep recursion bounded and manageable
    def json_value():
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_true,
            json_false,
            json_null,
        )

        def extend(children):
            # obj: '{' pair (',' pair)* '}' | '{}'
            # pair: STRING ':' value
            # arr: '[' value (',' value)* ']' | '[]'

            # pair strategy
            pair = st.tuples(json_string_st, children).map(lambda p: p[0] + ':' + p[1])

            obj_nonempty = st.lists(pair, min_size=1, max_size=3).map(lambda pairs: '{' + ','.join(pairs) + '}')
            obj_empty = st.just('{}')
            obj = st.one_of(obj_empty, obj_nonempty)

            arr_nonempty = st.lists(children, min_size=1, max_size=3).map(lambda vs: '[' + ','.join(vs) + ']')
            arr_empty = st.just('[]')
            arr = st.one_of(arr_empty, arr_nonempty)

            return st.one_of(obj, arr)

        return st.recursive(base, extend, max_leaves=10)

    val = draw(json_value())
    return val.encode('utf-8')