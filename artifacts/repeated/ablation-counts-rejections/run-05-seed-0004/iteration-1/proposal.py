from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy matching grammar: '"' (ESC | SAFECODEPOINT)* '"'
    # SAFECODEPOINT: any char except " \ and control chars (U+0000-U+001F)
    # ESC: \ followed by one of ["\/bfnrt] or \uXXXX
    # We'll generate strings that are mostly safe codepoints plus some escapes.

    # Characters allowed inside strings (excluding " and \ and control chars)
    safe_char = st.characters(
        blacklist_characters=['"', '\\'],
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    )

    # Escape sequences
    simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
    # Unicode escape: \uXXXX with HEX digits
    hex_digit = st.characters(min_codepoint=0x30, max_codepoint=0x39) | st.characters(min_codepoint=0x41, max_codepoint=0x46) | st.characters(min_codepoint=0x61, max_codepoint=0x66)
    unicode_escape = st.tuples(
        st.just('\\u'),
        st.text(st.characters(min_codepoint=0x30, max_codepoint=0x39) | st.characters(min_codepoint=0x41, max_codepoint=0x46) | st.characters(min_codepoint=0x61, max_codepoint=0x66), min_size=4, max_size=4)
    ).map(lambda t: t[0] + t[1])

    # Compose string content from safe chars and escapes
    string_char = st.one_of(
        safe_char.map(lambda c: c),
        simple_escapes,
        unicode_escape,
    )

    # Limit string length to keep output size bounded
    string_content = st.text(string_char, min_size=0, max_size=20)

    json_string = string_content.map(lambda s: '"' + s + '"')

    # NUMBER: '-'? INT ('.' [0-9]+)? EXP?
    # INT: '0' | [1-9][0-9]*
    # EXP: [Ee][+-]?[0-9]+

    # We'll build numbers as strings to preserve exact format.

    def number_strategy():
        sign = st.one_of(st.just(''), st.just('-'))
        int_part = st.one_of(
            st.just('0'),
            st.tuples(
                st.characters(min_codepoint=0x31, max_codepoint=0x39),
                st.text(st.characters(min_codepoint=0x30, max_codepoint=0x39), max_size=5)
            ).map(lambda t: t[0] + t[1])
        )
        frac_part = st.one_of(st.just(''), st.tuples(st.just('.'), st.text(st.characters(min_codepoint=0x30, max_codepoint=0x39), min_size=1, max_size=5)).map(lambda t: t[0] + t[1]))
        exp_part = st.one_of(
            st.just(''),
            st.tuples(
                st.sampled_from(['e', 'E']),
                st.one_of(st.just(''), st.sampled_from(['+', '-'])),
                st.text(st.characters(min_codepoint=0x30, max_codepoint=0x39), min_size=1, max_size=3)
            ).map(lambda t: t[0] + t[1] + t[2])
        )
        return st.tuples(sign, int_part, frac_part, exp_part).map(lambda parts: ''.join(parts))

    json_number = number_strategy()

    # Recursive JSON values: string, number, obj, arr, true, false, null
    # Use st.recursive with max depth and size bounded

    # Forward declare value strategy
    # We'll define obj and arr inside the recursive strategy

    def json_value():
        base = st.one_of(
            json_string,
            json_number,
            json_true,
            json_false,
            json_null,
        )

        # Recursive containers
        def extend_children(children):
            # pair: STRING ':' value
            pair = st.tuples(json_string, children).map(lambda t: t[0] + ':' + t[1])

            # obj: '{' pair (',' pair)* '}' or '{}'
            obj_nonempty = st.lists(pair, min_size=1, max_size=3).map(lambda pairs: '{' + ','.join(pairs) + '}')
            obj_empty = st.just('{}')
            obj = st.one_of(obj_empty, obj_nonempty)

            # arr: '[' value (',' value)* ']' or '[]'
            arr_nonempty = st.lists(children, min_size=1, max_size=3).map(lambda vals: '[' + ','.join(vals) + ']')
            arr_empty = st.just('[]')
            arr = st.one_of(arr_empty, arr_nonempty)

            return st.one_of(base, obj, arr)

        return st.recursive(base, extend_children, max_leaves=10)

    value = json_value()

    # The top-level json is value + EOF (we just produce value)
    json_text = value

    s = draw(json_text)
    return s.encode('utf-8')