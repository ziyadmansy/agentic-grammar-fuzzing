from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly matching the grammar, allowing safe codepoints and escapes
    # We'll generate strings with safe unicode codepoints excluding control chars and quotes/backslash
    # and also allow some escapes.
    def json_string():
        # safe characters excluding control chars, quote, backslash
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # escape sequences allowed: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        # We'll generate either safe chars or escapes
        def escape_seq():
            # choose one escape sequence
            esc_simple = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
            # unicode escape \uXXXX
            hex_digit = st.sampled_from('0123456789abcdefABCDEF')
            unicode_esc = st.tuples(
                st.just('\\u'),
                hex_digit, hex_digit, hex_digit, hex_digit
            ).map(lambda t: ''.join(t))
            return st.one_of(esc_simple, unicode_esc)

        # Compose string content: list of either safe chars or escapes
        # Limit length to keep size bounded
        content = st.lists(st.one_of(safe_chars.map(str), escape_seq()), max_size=20).map(''.join)
        return content.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # NUMBER: roughly matching the grammar
    # We'll use floats and ints converted to strings with JSON number format
    def json_number():
        # Generate numbers in a reasonable range to avoid huge strings
        # Use floats and ints, including negative and exponentials
        # We'll generate as string to avoid float repr issues
        def number_to_json(n):
            # Format number as JSON number string
            # Use repr for floats, str for ints
            if isinstance(n, int):
                return str(n)
            else:
                # format float with possible exponent
                return format(n, '.15g')
        # Generate int or float
        int_or_float = st.one_of(
            st.integers(min_value=-10**6, max_value=10**6),
            st.floats(min_value=-1e6, max_value=1e6, allow_infinity=False, allow_nan=False)
        )
        return int_or_float.map(number_to_json)

    json_number_st = json_number()

    # Recursive JSON value strategy
    # We'll use st.recursive to build obj and arr with bounded depth and size
    base_values = st.one_of(
        json_string_st,
        json_number_st,
        json_null,
        json_true,
        json_false,
    )

    # Forward declarations for obj and arr
    # obj: '{' pair (',' pair)* '}' | '{}'
    # pair: STRING ':' value
    # arr: '[' value (',' value)* ']' | '[]'

    # We define pair inside the recursive function to capture value strategy

    def json_obj(value_st):
        # pair: STRING ':' value
        pair = st.tuples(json_string_st, value_st).map(lambda t: f'{t[0]}:{t[1]}')
        # zero or more pairs separated by commas
        pairs = st.lists(pair, max_size=5).map(lambda ps: ','.join(ps))
        # full object
        return pairs.map(lambda s: '{' + s + '}' if s else '{}')

    def json_arr(value_st):
        # zero or more values separated by commas
        values = st.lists(value_st, max_size=5).map(lambda vs: ','.join(vs))
        return values.map(lambda s: '[' + s + ']' if s else '[]')

    # Recursive strategy for value including obj and arr
    json_value = st.recursive(
        base_values,
        lambda children: st.one_of(
            json_obj(children),
            json_arr(children),
        ),
        max_leaves=20,
    )

    # Compose full JSON with EOF (we just produce the JSON text)
    json_text = json_value

    # Draw one example and encode as bytes
    s = draw(json_text)
    return s.encode('utf-8')