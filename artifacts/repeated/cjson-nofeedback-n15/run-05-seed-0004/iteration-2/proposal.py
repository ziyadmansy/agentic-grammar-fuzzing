from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode them as JSON strings.
    # To keep it simple and safe, use st.text with a restricted charset.
    # We'll allow control chars escaped as \uXXXX or common escapes.
    # Hypothesis has a built-in json string strategy, but we implement our own.

    def json_string():
        # Characters allowed unescaped in JSON strings (SAFECODEPOINT)
        safe_chars = (
            " !#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"
        )
        # We'll allow these plus some escapes.
        # To keep it simple, generate strings from safe_chars only.
        # Length bounded to keep size small.
        return st.text(safe_chars, min_size=0, max_size=20).map(
            lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
        )

    json_string_st = json_string()

    # NUMBER strategy: generate JSON numbers as strings
    # Use Hypothesis floats and convert to JSON number strings.
    # We'll generate integers and floats with optional exponent.
    def json_number():
        # Generate numbers as strings matching the grammar
        # Use floats with limited range and precision
        # Also generate integers separately
        int_str = st.integers(min_value=-10**6, max_value=10**6).map(str)
        float_str = st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ).map(lambda f: format(f, ".6g"))
        # Combine int or float strings
        return st.one_of(int_str, float_str)

    json_number_st = json_number()

    # Recursive JSON value strategy
    # Use st.recursive to build obj and arr

    # Forward declaration for value
    # We'll build value as a strategy of bytes (utf-8 encoded strings)

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string_st,
        json_number_st,
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: obj and arr
    # obj: '{' pair (',' pair)* '}' or '{}'
    # pair: STRING ':' value
    # arr: '[' value (',' value)* ']' or '[]'

    # We'll define pair as a tuple of (string, value)
    # But since we want bytes output, we will build strings and then encode at the end

    # To keep recursion bounded, limit max depth and max size

    def json_value():
        # We'll define a recursive strategy returning strings (not bytes yet)
        # so we can compose easily, then encode at the end.

        # Forward declaration
        return st.deferred(lambda: json_value_strategy)

    # pair strategy: STRING ':' value
    def json_pair():
        return st.tuples(json_string_st, json_value()).map(
            lambda p: f"{p[0]}:{p[1]}"
        )

    # obj strategy
    def json_obj():
        # empty object or object with 1-3 pairs
        pairs = st.lists(json_pair(), min_size=0, max_size=3)
        return pairs.map(
            lambda ps: "{" + ",".join(ps) + "}" if ps else "{}"
        )

    # arr strategy
    def json_arr():
        # empty array or array with 1-3 values
        values = st.lists(json_value(), min_size=0, max_size=3)
        return values.map(
            lambda vs: "[" + ",".join(vs) + "]" if vs else "[]"
        )

    # Compose the recursive value strategy
    json_value_strategy = st.recursive(
        base_values,
        lambda children: st.one_of(json_obj(), json_arr()),
        max_leaves=10,
    )

    # Draw the final JSON string and encode as utf-8 bytes
    json_str = draw(json_value_strategy)
    return json_str.encode("utf-8")