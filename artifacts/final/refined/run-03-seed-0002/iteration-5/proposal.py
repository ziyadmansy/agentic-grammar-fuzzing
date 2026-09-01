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
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t'
        ])
        # Unicode escape \uXXXX
        hex_digit = st.sampled_from("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: "".join(t))

        # Either a safe char or an escape sequence
        char = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Build string content of length 0..20 (bounded)
        content = st.lists(char, max_size=20).map("".join)
        return content.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # NUMBER strategy: produce valid JSON numbers as strings
    def json_number():
        # Use Hypothesis built-in floats, but convert to JSON number strings
        # Limit floats to finite, no NaN or inf
        # Also include integers
        # We'll generate strings matching the NUMBER grammar
        # Use floats with limited exponent range and decimal places
        def float_to_json_number(f):
            # Convert float to JSON number string without trailing .0 if integer
            if f == float('inf') or f == float('-inf') or f != f:
                # fallback to 0
                return "0"
            s = format(f, '.15g')
            # Ensure exponent uses E not e
            s = s.replace('e', 'E')
            return s

        # Generate floats in a reasonable range to avoid huge exponents
        floats = st.floats(
            allow_infinity=False,
            allow_nan=False,
            width=32,
            min_value=-1e10,
            max_value=1e10,
        ).map(float_to_json_number)

        # Also generate integers as strings
        integers = st.integers(min_value=-10**10, max_value=10**10).map(str)

        return st.one_of(floats, integers)

    json_number_st = json_number()

    # Forward declaration for recursive structures
    # We'll define value recursively with bounded depth
    # Use st.recursive to build obj and arr

    # obj: '{' pair (',' pair)* '}' | '{}'
    # pair: STRING ':' value

    # arr: '[' value (',' value)* ']' | '[]'

    # Define pair strategy
    def pair(value_st):
        return st.tuples(json_string_st, value_st).map(lambda t: f"{t[0]}:{t[1]}")

    # Recursive value strategy
    def value_strategy():
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_null,
            json_true,
            json_false,
        )

        def extend(value_st):
            obj_st = st.lists(pair(value_st), max_size=5).map(
                lambda pairs: "{" + ",".join(pairs) + "}" if pairs else "{}"
            )
            arr_st = st.lists(value_st, max_size=5).map(
                lambda vals: "[" + ",".join(vals) + "]" if vals else "[]"
            )
            return st.one_of(obj_st, arr_st)

        return st.recursive(base, extend, max_leaves=10)

    json_value_st = value_strategy()

    # Compose full JSON with EOF
    json_full = json_value_st.map(lambda s: s)

    s = draw(json_full)
    return s.encode("utf-8")