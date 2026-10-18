from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: simple safe strings with escapes
    def json_string():
        # Characters allowed inside strings (excluding control chars and " \)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escape sequences
        escape_seq = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t',
        ])
        # Unicode escape: \uXXXX
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: "".join(t))

        # Either a safe char or an escape sequence
        char_or_escape = st.one_of(
            safe_char.map(lambda c: c),
            escape_seq,
            unicode_escape,
        )

        # Build string content with length 0 to 20
        content = st.lists(char_or_escape, max_size=20).map("".join)
        return content.map(lambda s: f'"{s}"')

    # NUMBER strategy: generate numbers as strings matching grammar
    def json_number():
        # Use hypothesis floats but convert to JSON number string
        # Limit size to avoid huge exponents or decimals
        # We'll generate strings directly to better control format
        int_part = st.one_of(
            st.just("0"),
            st.tuples(
                st.characters("123456789", min_codepoint=49, max_codepoint=57),
                st.text(st.characters("0123456789"), max_size=5)
            ).map(lambda t: t[0] + t[1])
        )
        frac_part = st.one_of(st.just(""), st.tuples(st.just("."), st.text(st.characters("0123456789"), min_size=1, max_size=5)).map(lambda t: t[0] + t[1]))
        exp_part = st.one_of(
            st.just(""),
            st.tuples(
                st.sampled_from(["e", "E"]),
                st.one_of(st.just("+"), st.just("-"), st.just("")),
                st.text(st.characters("0123456789"), min_size=1, max_size=3)
            ).map(lambda t: t[0] + t[1] + t[2])
        )
        sign = st.one_of(st.just(""), st.just("-"))
        return st.tuples(sign, int_part, frac_part, exp_part).map(lambda t: "".join(t))

    # Recursive JSON value strategy
    def json_value():
        # Forward declaration for recursion
        return st.deferred(lambda: json_value_inner())

    # Compose object and array with bounded recursion
    def json_object():
        # pair: STRING ':' value
        pair = st.tuples(json_string(), json_value()).map(lambda t: f"{t[0]}:{t[1]}")
        # 0 to 5 pairs
        pairs = st.lists(pair, max_size=5)
        return pairs.map(lambda ps: "{" + (",".join(ps) if ps else "") + "}")

    def json_array():
        # 0 to 5 values
        values = st.lists(json_value(), max_size=5)
        return values.map(lambda vs: "[" + (",".join(vs) if vs else "") + "]")

    def json_value_inner():
        # Weighted choice to favor primitives and small structures
        return st.recursive(
            st.one_of(
                json_string(),
                json_number(),
                json_true,
                json_false,
                json_null,
            ),
            lambda children: st.one_of(
                json_object(),
                json_array(),
            ),
            max_leaves=10,
        )

    # Compose full JSON with EOF
    json_str = json_value().map(lambda s: s)

    s = draw(json_str)
    return s.encode("utf-8")