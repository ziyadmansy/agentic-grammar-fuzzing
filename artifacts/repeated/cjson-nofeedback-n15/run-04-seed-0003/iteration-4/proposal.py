from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and backslash/quote)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control characters
        )
        # Escaped characters
        escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape sequences
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.builds(
            lambda a,b,c,d: "\\u" + a + b + c + d,
            hex_digit, hex_digit, hex_digit, hex_digit
        )
        # Either safe char or escape sequence
        char = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Compose string content with length limit
        content = st.text(char, min_size=0, max_size=20)
        return content.map(lambda s: '"' + s + '"')

    json_string_st = json_string()

    # NUMBER strategy: produce valid JSON numbers as strings
    def json_number():
        # Use hypothesis floats but convert to JSON number strings
        # Limit floats to finite, non-NaN, non-inf
        # Use decimal notation or exponent notation
        # We'll build numbers from components to better control format
        sign = st.one_of(st.just(""), st.just("-"))
        int_part = st.one_of(st.just("0"), st.from_regex(r"[1-9][0-9]*", fullmatch=True))
        frac_part = st.one_of(st.just(""), st.builds(lambda f: "." + f, st.from_regex(r"[0-9]+", fullmatch=True)))
        exp_part = st.one_of(
            st.just(""),
            st.builds(
                lambda e, s, d: e + s + d,
                st.sampled_from(["e", "E"]),
                st.sampled_from(["", "+", "-"]),
                st.from_regex(r"[0-9]+", fullmatch=True),
            ),
        )
        return st.builds(lambda s,i,f,e: s+i+f+e, sign, int_part, frac_part, exp_part)

    json_number_st = json_number()

    # Recursive JSON value strategy
    # Use st.recursive with base = primitives, containers = obj and arr

    # Forward declaration for value
    # We'll define value inside this function to keep scope clean

    def json_value():
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_null,
            json_true,
            json_false,
        )

        # obj: '{' pair (',' pair)* '}' or '{}'
        # pair: STRING ':' value
        # arr: '[' value (',' value)* ']' or '[]'

        # To avoid infinite recursion, limit max depth and size

        def json_obj():
            # pair: STRING ':' value
            # limit number of pairs to max 3
            pairs = st.lists(
                st.tuples(json_string_st, json_value()),
                max_size=3,
                unique_by=lambda p: p[0],  # unique keys
            )
            def pairs_to_obj(pairs):
                if not pairs:
                    return "{}"
                inner = ",".join(f"{k}:{v}" for k,v in pairs)
                return "{" + inner + "}"
            return pairs.map(pairs_to_obj)

        def json_arr():
            # list of values, max size 3
            values = st.lists(json_value(), max_size=3)
            def values_to_arr(values):
                if not values:
                    return "[]"
                inner = ",".join(values)
                return "[" + inner + "]"
            return values.map(values_to_arr)

        return st.recursive(
            base,
            lambda children: st.one_of(json_obj(), json_arr()),
            max_leaves=10,
        )

    val = json_value()

    # Compose full JSON text: value + EOF (implicit)
    json_text = val

    s = draw(json_text)
    return s.encode("utf-8")