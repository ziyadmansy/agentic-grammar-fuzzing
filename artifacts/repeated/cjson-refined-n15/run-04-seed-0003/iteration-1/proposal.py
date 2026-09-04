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
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\b', r'\f', r'\n', r'\r', r'\t',
        ])
        # Unicode escape \uXXXX
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: "".join(t))

        # Mix safe chars and escapes/unicode escapes
        char_piece = st.one_of(
            safe_char.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Build string content with length limit to keep size bounded
        content = st.lists(char_piece, max_size=20).map("".join)
        return content.map(lambda s: f'"{s}"')

    # NUMBER strategy: use Hypothesis floats and ints, then convert to JSON number strings
    def json_number():
        # Generate int or float, then convert to JSON number string
        # Limit range to keep numbers reasonable
        number = st.one_of(
            st.integers(min_value=-10**6, max_value=10**6),
            st.floats(
                allow_infinity=False,
                allow_nan=False,
                width=32,
                min_value=-1e6,
                max_value=1e6,
            ),
        )
        def to_json_number(n):
            # Format floats with minimal representation
            if isinstance(n, float):
                # Use repr to get shortest representation
                s = repr(n)
                # JSON requires decimal point for floats
                if '.' not in s and 'e' not in s and 'E' not in s:
                    s += ".0"
                return s
            else:
                return str(n)
        return number.map(to_json_number)

    # Forward declaration for recursive value
    # We'll use st.recursive to build nested objects and arrays

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string(),
        json_number(),
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: objects and arrays
    # To keep size bounded, limit max depth and max number of elements

    def json_value():
        # Compose recursive strategy for value
        # Use st.recursive with base_values and containers

        # Pair: STRING ':' value
        def json_pair():
            return st.tuples(json_string(), json_value()).map(
                lambda t: f"{t[0]}:{t[1]}"
            )

        # Object: '{' pair (',' pair)* '}' or '{}'
        json_obj = st.lists(json_pair(), max_size=5).map(
            lambda pairs: "{" + ",".join(pairs) + "}" if pairs else "{}"
        )

        # Array: '[' value (',' value)* ']' or '[]'
        json_arr = st.lists(json_value(), max_size=5).map(
            lambda values: "[" + ",".join(values) + "]" if values else "[]"
        )

        containers = st.one_of(json_obj, json_arr)

        return st.recursive(base_values, lambda children: containers, max_leaves=10)

    # Compose full JSON: value + EOF (EOF is implicit)
    json_str = draw(json_value())

    return json_str.encode("utf-8")