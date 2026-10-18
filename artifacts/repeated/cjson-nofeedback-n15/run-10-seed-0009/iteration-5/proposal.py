from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and " \)
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
        chunk = st.one_of(
            safe_char.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Build string content with length 0 to 20
        content = st.lists(chunk, max_size=20).map("".join)
        return content.map(lambda s: f'"{s}"')

    # NUMBER strategy: produce valid JSON numbers
    def json_number():
        # Use Hypothesis floats converted to JSON number strings with bounded size
        # To keep near-valid, also allow integers and floats with exponent
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        frac_part = st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)
            .map(lambda f: f"{f:.6f}".lstrip("0"))
        )
        # To keep it simple and valid, just use Hypothesis floats converted to JSON string
        # But to keep control, build number strings manually:
        def number_str():
            sign = st.one_of(st.just(""), st.just("-"))
            int_ = st.one_of(
                st.just("0"),
                st.integers(min_value=1, max_value=10**6).map(str)
            )
            frac = st.one_of(
                st.just(""),
                st.tuples(st.just("."), st.text(min_size=1, max_size=6, alphabet="0123456789"))
                .map(lambda t: "".join(t))
            )
            exp = st.one_of(
                st.just(""),
                st.tuples(
                    st.sampled_from(["e", "E"]),
                    st.one_of(st.just("+"), st.just("-"), st.just("")),
                    st.integers(min_value=0, max_value=99).map(lambda x: f"{x}")
                ).map(lambda t: "".join(t))
            )
            return st.tuples(sign, int_, frac, exp).map(lambda parts: "".join(parts))
        return number_str()

    # Recursive JSON value strategy
    def json_value():
        # Forward declaration for recursion
        return st.deferred(lambda: json_value_inner())

    # Compose object and array with bounded recursion depth
    def json_object():
        # pair: STRING ':' value
        pair = st.tuples(json_string(), st.just(":"), json_value())
        # pairs list, max 5 pairs to keep size bounded
        pairs = st.lists(pair, max_size=5)
        return pairs.map(
            lambda ps: "{" + ",".join(k + v + val for (k, v, val) in ps) + "}" if ps else "{}"
        )

    def json_array():
        # list of values, max 5 elements
        values = st.lists(json_value(), max_size=5)
        return values.map(
            lambda vs: "[" + ",".join(vs) + "]" if vs else "[]"
        )

    def json_value_inner():
        # Compose all value types, bias towards simpler ones to keep size small
        return st.one_of(
            json_string(),
            json_number(),
            json_object(),
            json_array(),
            json_true,
            json_false,
            json_null,
        )

    # Draw a JSON value and encode as bytes
    s = draw(json_value())
    return s.encode("utf-8")