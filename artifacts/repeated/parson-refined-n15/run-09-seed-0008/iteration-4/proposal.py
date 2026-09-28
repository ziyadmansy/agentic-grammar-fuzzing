from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON strings: use ASCII printable except control and backslash/quote for simplicity
    # We allow some escapes to keep near-valid cases
    def json_string():
        # Characters allowed inside strings (excluding control chars, quote, backslash)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escape sequences: simple ones and unicode escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \uXXXX
        hex_digit = st.sampled_from("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: "".join(t))

        # Mix safe chars and escapes/unicode escapes
        char = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Generate string length bounded to keep size reasonable
        content = st.lists(char, min_size=0, max_size=20).map("".join)
        return content.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # JSON numbers: use Hypothesis built-in floats and ints, then convert to JSON number strings
    def json_number():
        # Generate int or float strings matching JSON number grammar
        # Use floats with finite values only
        int_part = st.integers(min_value=-(10**6), max_value=10**6).map(str)
        frac_part = st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False).map(
                lambda f: f"{f}".lstrip("0") if '.' in f"{f}" else ""
            ),
        )
        # Instead of complicated float formatting, use Hypothesis floats and format manually
        # But to keep it simple and valid, just use Hypothesis floats converted to JSON number strings
        # We'll generate floats with limited precision and convert to string
        float_st = st.floats(
            min_value=-(10**6), max_value=10**6,
            allow_infinity=False, allow_nan=False
        ).map(lambda f: format(f, '.6g'))

        # Combine int or float strings
        return st.one_of(int_part, float_st)

    json_number_st = json_number()

    # Recursive JSON values
    # Use st.recursive to build obj and arr with bounded depth and size
    base = st.one_of(
        json_string_st,
        json_number_st,
        json_null,
        json_true,
        json_false,
    )

    # Forward declarations for obj and arr to be used inside recursive
    # obj: {"pair", ...} or {}
    # pair: STRING : value
    # arr: [value, ...] or []

    # We'll define pair inside the recursive function to avoid circularity issues

    def json_value():
        # Compose pairs for obj
        pair = st.tuples(json_string_st, json_value()).map(lambda p: f"{p[0]}:{p[1]}")

        obj = st.one_of(
            st.just("{}"),
            st.lists(pair, min_size=1, max_size=5).map(lambda pairs: "{" + ",".join(pairs) + "}"),
        )

        arr = st.one_of(
            st.just("[]"),
            st.lists(json_value(), min_size=1, max_size=5).map(lambda vals: "[" + ",".join(vals) + "]"),
        )

        return st.one_of(base, obj, arr)

    # Use st.recursive to build nested JSON values with bounded depth and size
    json_val = st.recursive(
        base,
        lambda children: st.one_of(
            # object
            st.lists(
                st.tuples(json_string_st, children),
                min_size=1,
                max_size=5
            ).map(lambda pairs: "{" + ",".join(f"{k}:{v}" for k, v in pairs) + "}"),
            # array
            st.lists(children, min_size=1, max_size=5).map(lambda vals: "[" + ",".join(vals) + "]"),
        ),
        max_leaves=20,
    )

    # Draw the final JSON string and encode as UTF-8 bytes
    s = draw(json_val)
    return s.encode("utf-8")