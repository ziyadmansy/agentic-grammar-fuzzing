from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then JSON-encode them using repr-like escapes.
    # But since repr is not JSON, we build a string with escapes manually.
    # To keep it simple, use Hypothesis text with safe characters and escape quotes and backslashes.
    def json_string():
        # safe codepoints exclude control chars and quotes/backslash
        safe_chars = (
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # Compose string with some escapes inserted
        # We'll generate a list of chars or escapes, then join
        esc_chars = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Compose a list of either safe char or escape sequence
        pieces = st.lists(st.one_of(safe_chars.map(lambda c: c), esc_chars), max_size=20)
        return pieces.map(lambda chars: '"' + ''.join(chars) + '"')

    json_string_st = json_string()

    # NUMBER strategy: generate valid JSON numbers as strings
    # Use Hypothesis floats converted to JSON number strings with constraints
    def json_number():
        # Generate floats with limited exponent and decimal places, then convert to string
        # Also generate integers as strings
        int_str = st.integers(min_value=-10**6, max_value=10**6).map(str)
        float_str = st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ).map(lambda f: format(f, '.6g'))  # compact representation
        return st.one_of(int_str, float_str)

    json_number_st = json_number()

    # Forward declaration for recursive structures
    # We'll build value recursively with bounded depth
    def json_value():
        # Compose value strategy recursively
        # Use recursive to limit depth and size
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_true,
            json_false,
            json_null,
        )

        # Recursive containers: obj and arr
        def obj_strategy():
            # pair: STRING ':' value
            pair = st.tuples(json_string_st, json_value()).map(lambda p: f"{p[0]}:{p[1]}")
            # object: '{' pair (',' pair)* '}' or '{}'
            return st.lists(pair, max_size=5).map(
                lambda pairs: "{" + ",".join(pairs) + "}" if pairs else "{}"
            )

        def arr_strategy():
            # array: '[' value (',' value)* ']' or '[]'
            return st.lists(json_value(), max_size=5).map(
                lambda values: "[" + ",".join(values) + "]" if values else "[]"
            )

        return st.recursive(
            base,
            lambda children: st.one_of(obj_strategy(), arr_strategy()),
            max_leaves=10,
        )

    json_str = draw(json_value())
    return json_str.encode("utf-8")