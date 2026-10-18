from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: simple ASCII strings with safe codepoints and escapes
    # To keep it simple and valid, limit length and escapes
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escapes: limited set
        escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Either safe char or escape sequence
        string_char = st.one_of(safe_chars, escapes)
        # Compose string of length 0..20
        return string_char.flatmap(
            lambda c: st.text(string_char, min_size=0, max_size=19).map(lambda s: c + s)
        ).map(lambda s: '"' + s + '"')

    json_string_strat = json_string()

    # NUMBER strategy: integers and floats with optional exponent
    # Use Hypothesis floats converted to JSON number strings, but restrict to finite numbers
    def json_number():
        # Generate float or int as string
        # To keep it simple, generate int or float strings directly
        int_str = st.integers(min_value=-10**6, max_value=10**6).map(str)
        float_str = st.floats(
            allow_nan=False, allow_infinity=False,
            width=32, min_value=-1e6, max_value=1e6
        ).map(lambda f: format(f, '.6g'))
        return st.one_of(int_str, float_str)

    json_number_strat = json_number()

    # Recursive JSON value strategy
    # Use st.recursive to build nested objects and arrays with bounded depth and size
    base = st.one_of(
        json_string_strat,
        json_number_strat,
        json_null,
        json_true,
        json_false,
    )

    # Forward declarations for obj and arr to be used inside recursive
    # pair: STRING ':' value
    def json_pair():
        return st.tuples(json_string_strat, value).map(lambda p: f"{p[0]}:{p[1]}")

    def json_obj():
        # empty or pairs separated by commas
        # limit number of pairs to max 3 to keep size bounded
        pairs = st.lists(json_pair(), max_size=3)
        return pairs.map(lambda ps: "{" + (",".join(ps) if ps else "") + "}")

    def json_arr():
        # empty or values separated by commas, max 3 elements
        arr_vals = st.lists(value, max_size=3)
        return arr_vals.map(lambda vs: "[" + (",".join(vs) if vs else "") + "]")

    # Recursive value strategy
    value = st.recursive(
        base,
        lambda children: st.one_of(
            json_obj(),
            json_arr(),
        ),
        max_leaves=10,
    )

    # Draw a value and encode as bytes
    val = draw(value)
    return val.encode("utf-8")