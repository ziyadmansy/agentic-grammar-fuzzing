from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, '.15g'))
    # JSON strings with escapes and safe codepoints
    # We mimic the grammar: STRING : '"' (ESC | SAFECODEPOINT)* '"'
    # SAFECODEPOINT: any char except " \ and control chars (0x00-0x1F)
    # ESC: \ followed by one of ["\/bfnrt] or \uXXXX
    # We'll generate strings with a mix of safe chars and escapes
    def json_string_chars():
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape \uXXXX with hex digits
        hex_digit = st.sampled_from('0123456789abcdefABCDEF')
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))
        escape = st.one_of(simple_escapes, unicode_escape)
        # Mix safe chars and escapes
        return st.lists(st.one_of(safe_chars.map(lambda c: c), escape), max_size=20).map(''.join)

    json_string = json_string_chars().map(lambda s: f'"{s}"')

    # Recursive JSON values: string, number, obj, arr, true, false, null
    # We'll use st.recursive with a max depth and max size to keep bounded

    # Forward declaration for recursive
    def json_value():
        base = st.one_of(
            json_string,
            json_number,
            json_true,
            json_false,
            json_null,
        )
        # Recursive containers: obj and arr
        # obj: '{' pair (',' pair)* '}' or '{}'
        # pair: STRING ':' value
        # arr: '[' value (',' value)* ']' or '[]'

        # We'll define pair inside to avoid circular import issues
        def json_pair():
            return st.tuples(json_string, json_value()).map(lambda p: f'{p[0]}:{p[1]}')

        # obj: either empty or pairs separated by commas
        json_obj = st.one_of(
            st.just('{}'),
            st.lists(json_pair(), max_size=5).map(lambda pairs: '{' + ','.join(pairs) + '}')
        )

        # arr: either empty or values separated by commas
        json_arr = st.one_of(
            st.just('[]'),
            st.lists(json_value(), max_size=5).map(lambda values: '[' + ','.join(values) + ']')
        )

        return st.one_of(base, json_obj, json_arr)

    # Use recursive to limit depth and size
    json_val_strategy = st.recursive(
        st.one_of(json_string, json_number, json_true, json_false, json_null),
        lambda children: st.one_of(
            st.lists(children, max_size=5).map(lambda vs: '[' + ','.join(vs) + ']'),
            st.lists(
                st.tuples(json_string, children),
                max_size=5
            ).map(lambda pairs: '{' + ','.join(f'{k}:{v}' for k, v in pairs) + '}')
        ),
        max_leaves=20,
    )

    # Compose full JSON with EOF (we just produce the JSON text)
    json_text = draw(json_val_strategy)

    # Return as bytes (UTF-8)
    return json_text.encode('utf-8')