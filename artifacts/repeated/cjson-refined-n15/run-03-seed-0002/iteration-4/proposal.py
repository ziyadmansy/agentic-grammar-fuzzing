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
    # We'll generate strings with safe unicode codepoints and some escapes.

    # Characters allowed inside strings (excluding control chars and " \)
    safe_chars = st.characters(
        blacklist_characters=['"', '\\'],
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    )

    # Escape sequences
    simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
    # Unicode escape \uXXXX
    hex_digit = st.sampled_from("0123456789abcdefABCDEF")
    unicode_escape = st.tuples(
        st.just('\\u'),
        hex_digit, hex_digit, hex_digit, hex_digit
    ).map(lambda t: ''.join(t))

    # Either a safe char or an escape sequence
    json_string_char = st.one_of(
        safe_chars.map(lambda c: c),
        simple_escapes,
        unicode_escape,
    )

    # Compose string content with length limit to keep size bounded
    json_string_content = st.lists(json_string_char, min_size=0, max_size=20).map(''.join)
    json_string = json_string_content.map(lambda s: f'"{s}"')

    # NUMBER strategy matching grammar NUMBER : '-'? INT ('.' [0-9]+)? EXP? ;
    # We'll reuse Hypothesis floats but convert to JSON number strings.

    def number_to_json(n: float) -> str:
        # Format float to JSON number string without trailing .0 if integer
        if n == float('inf') or n == float('-inf') or n != n:
            # NaN or inf not valid JSON numbers, fallback to 0
            return "0"
        s = repr(n)
        # repr can produce scientific notation, which is valid JSON
        return s

    json_number = st.floats(
        allow_infinity=False,
        allow_nan=False,
        width=32,
        min_value=-1e10,
        max_value=1e10,
    ).map(number_to_json)

    # Recursive JSON value strategy
    # We'll define a recursive strategy for value, obj, arr

    # Forward declaration for recursion
    json_value = st.deferred(lambda: json_value_inner)

    # Pair: STRING ':' value
    json_pair = st.tuples(json_string, json_value).map(lambda t: f'{t[0]}:{t[1]}')

    # Object: '{' pair (',' pair)* '}' or '{}'
    json_obj = st.recursive(
        st.just('{}'),
        lambda children: st.builds(
            lambda pairs: '{' + ','.join(pairs) + '}',
            st.lists(json_pair, min_size=1, max_size=5)
        ),
        max_leaves=5,
    )

    # Array: '[' value (',' value)* ']' or '[]'
    json_arr = st.recursive(
        st.just('[]'),
        lambda children: st.builds(
            lambda values: '[' + ','.join(values) + ']',
            st.lists(json_value, min_size=1, max_size=5)
        ),
        max_leaves=5,
    )

    # Compose json_value_inner with all options
    json_value_inner = st.one_of(
        json_string,
        json_number,
        json_obj,
        json_arr,
        json_true,
        json_false,
        json_null,
    )

    # Draw a JSON value and encode as UTF-8 bytes
    val = draw(json_value)
    return val.encode('utf-8')