from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly matching grammar, with safe codepoints and escapes
    # We'll generate strings with safe unicode codepoints and some escapes
    # to preserve validity and near-validity.
    # Use a small subset of escapes for simplicity.
    def json_string():
        # Characters allowed inside strings (excluding control chars and " \)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        simple_escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \uXXXX
        def unicode_escape():
            hex_digit = st.sampled_from('0123456789abcdefABCDEF')
            return st.tuples(hex_digit, hex_digit, hex_digit, hex_digit).map(
                lambda t: '\\u' + ''.join(t)
            )
        escape = st.one_of(simple_escapes, unicode_escape())
        # Mix safe chars and escapes
        # To keep it simple, generate a list of length 0..10 of either safe char or escape
        char_or_escape = st.one_of(
            safe_chars.map(lambda c: c),
            escape
        )
        # Compose string content
        content = st.lists(char_or_escape, max_size=10).map(''.join)
        return content.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # NUMBER: roughly matching grammar
    # We'll generate numbers as strings to preserve JSON number format
    # Use floats and ints, then convert to string
    def json_number():
        # Generate int or float or exponent form as string
        # Use floats with limited precision to avoid huge strings
        # Also allow negative numbers
        def number_to_str(n):
            # Format number to JSON number string
            # Use repr to get a valid JSON number string
            # But repr can produce scientific notation, which is valid
            return repr(n)
        # Generate floats and ints in a reasonable range
        number = st.one_of(
            st.integers(min_value=-10**6, max_value=10**6).map(str),
            st.floats(min_value=-1e6, max_value=1e6, allow_infinity=False, allow_nan=False).map(number_to_str),
        )
        return number

    json_number_st = json_number()

    # Recursive JSON value strategy
    # Use st.recursive to build obj and arr with bounded depth and size
    # We limit max depth to keep output sizes bounded

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string_st,
        json_number_st,
        json_true,
        json_false,
        json_null,
    )

    # Forward declarations for obj and arr
    # We'll define them inside a function to use recursion

    def json_value():
        # Recursive strategy for JSON values
        # Compose obj and arr from base_values and recursive calls
        # Limit max depth and size
        return st.recursive(
            base_values,
            lambda children: st.one_of(
                json_object(children),
                json_array(children),
            ),
            max_leaves=10,
        )

    def json_object(children):
        # pair: STRING ':' value
        # pair list: pair (',' pair)*
        # empty object: '{}'
        # non-empty object: '{' pair (',' pair)* '}'
        # We'll generate 0..5 pairs to keep size bounded
        pair = st.tuples(json_string_st, children).map(lambda t: f'{t[0]}:{t[1]}')
        pairs = st.lists(pair, max_size=5)
        return pairs.map(
            lambda ps: '{' + (','.join(ps) if ps else '') + '}'
        )

    def json_array(children):
        # array: '[' value (',' value)* ']' or '[]'
        # Generate 0..5 elements
        elements = st.lists(children, max_size=5)
        return elements.map(
            lambda es: '[' + (','.join(es) if es else '') + ']'
        )

    # Generate a full JSON text (value + EOF)
    json_text = json_value()

    # Draw the JSON string and encode as bytes
    s = draw(json_text)
    return s.encode('utf-8')