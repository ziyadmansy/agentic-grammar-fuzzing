from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON tokens
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # SAFECODEPOINT: any char except " \ and control chars (0x00-0x1F)
    # We'll generate unicode codepoints excluding control chars and " \ 
    def json_string_chars():
        # safe codepoints: exclude control chars and " and \
        # range: 0x20-0x10FFFF except " (0x22) and \ (0x5C)
        # We'll generate from BMP mostly for simplicity
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0xD7FF,
        )
        # Also allow some common escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \uXXXX with hex digits
        hex_digit = st.sampled_from('0123456789abcdefABCDEF')
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))
        # Compose a character as either safe char or escape or unicode escape
        return st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape,
        )

    # Compose string content with length bounded to keep size reasonable
    string_content = st.lists(json_string_chars(), min_size=0, max_size=20).map(''.join)
    json_string = string_content.map(lambda s: f'"{s}"')

    # NUMBER strategy: produce valid JSON numbers
    # We'll generate floats and ints as strings matching the grammar
    def json_number():
        # integer part
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        # fraction part optional
        fraction_part = st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)
            .map(lambda f: f"{f}".lstrip("0") if '.' in f"{f}" else "")
        )
        # exponent part optional
        exp_part = st.one_of(
            st.just(""),
            st.tuples(
                st.sampled_from(['e', 'E']),
                st.sampled_from(['+', '-', '']),
                st.integers(min_value=0, max_value=99)
            ).map(lambda t: f"{t[0]}{t[1]}{t[2]}")
        )
        # sign optional
        sign = st.one_of(st.just(""), st.just("-"))
        # Compose number string
        return st.tuples(sign, int_part, fraction_part, exp_part).map(
            lambda t: t[0] + t[1] + t[2] + t[3]
        )

    json_number_str = json_number()

    # Forward declaration for recursive value
    # We'll use st.recursive to build nested objects and arrays

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string,
        json_number_str,
        json_true,
        json_false,
        json_null,
    )

    # Recursive strategy for value: base or obj or arr
    def json_value():
        # obj and arr are recursive
        # obj: {} or { pair (, pair)* }
        # pair: STRING : value
        # arr: [] or [ value (, value)* ]

        # pair strategy: STRING : value
        # STRING keys are json_string (already quoted)
        # value is recursive json_value

        # To avoid infinite recursion, limit max depth and size
        max_depth = 3

        def pairs_strategy(depth):
            if depth <= 0:
                return st.just([])
            # pairs: list of pair strings
            # pair: STRING : value
            return st.lists(
                st.tuples(
                    json_string,
                    json_value_strategy(depth - 1)
                ).map(lambda kv: f"{kv[0]}:{kv[1]}"),
                min_size=1,
                max_size=3
            )

        def obj_strategy(depth):
            if depth <= 0:
                return st.just("{}")
            return st.one_of(
                st.just("{}"),
                pairs_strategy(depth).map(lambda pairs: "{" + ",".join(pairs) + "}")
            )

        def arr_strategy(depth):
            if depth <= 0:
                return st.just("[]")
            return st.one_of(
                st.just("[]"),
                st.lists(
                    json_value_strategy(depth - 1),
                    min_size=1,
                    max_size=4
                ).map(lambda vals: "[" + ",".join(vals) + "]")
            )

        def json_value_strategy(depth):
            if depth <= 0:
                return base_values
            return st.one_of(
                base_values,
                obj_strategy(depth),
                arr_strategy(depth),
            )

        return json_value_strategy(max_depth)

    # Compose full json text with EOF
    json_text = json_value()

    # Draw the json string and encode as bytes
    s = draw(json_text)
    return s.encode("utf-8")