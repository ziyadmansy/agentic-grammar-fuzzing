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
        # Escapes: \" \\ \/ \b \f \n \r \t and \uXXXX
        simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: "".join(t))
        escape = st.one_of(simple_escapes, unicode_escape)
        # Compose string content from safe chars and escapes
        string_char = st.one_of(safe_char.map(lambda c: c), escape)
        # Limit length to keep size bounded
        content = st.text(string_char, min_size=0, max_size=20)
        return content.map(lambda s: f'"{s}"')

    # NUMBER strategy: integers and floats with optional exponent
    def json_number():
        int_part = st.one_of(
            st.just("0"),
            st.tuples(st.sampled_from("123456789"), st.text(st.characters("0123456789"), max_size=5)).map(
                lambda t: t[0] + t[1]
            ),
        )
        frac_part = st.one_of(st.just(""), st.tuples(st.just("."), st.text(st.characters("0123456789"), min_size=1, max_size=5)).map(lambda t: "".join(t)))
        exp_part = st.one_of(
            st.just(""),
            st.tuples(
                st.sampled_from("eE"),
                st.one_of(st.just("+"), st.just("-"), st.just("")),
                st.text(st.characters("0123456789"), min_size=1, max_size=3),
            ).map(lambda t: "".join(t)),
        )
        sign = st.one_of(st.just(""), st.just("-"))
        return st.tuples(sign, int_part, frac_part, exp_part).map(lambda t: "".join(t))

    # Recursive JSON value strategy
    def json_value():
        # Forward declaration for recursion
        return st.deferred(lambda: json_value_inner())

    # Compose object: { pair (, pair)* } or {}
    def json_object():
        # pair: STRING : value
        pair = st.tuples(json_string(), st.just(":"), json_value()).map(lambda t: t[0] + t[1] + t[2])
        # list of pairs, max 3 pairs to keep size bounded
        pairs = st.lists(pair, max_size=3)
        # Compose object string
        return pairs.map(lambda ps: "{" + (",".join(ps) if ps else "") + "}")

    # Compose array: [ value (, value)* ] or []
    def json_array():
        values = st.lists(json_value(), max_size=3)
        return values.map(lambda vs: "[" + (",".join(vs) if vs else "") + "]")

    def json_value_inner():
        # Compose all possible JSON values
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