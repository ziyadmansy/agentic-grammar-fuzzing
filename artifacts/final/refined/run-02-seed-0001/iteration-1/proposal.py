from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: simplified safe strings with escapes
    # Use ASCII printable except control and backslash/quote, plus some escapes
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars, quote, backslash)
        safe_chars = st.characters(
            blacklist_characters=['\\', '"'],
            min_codepoint=0x20,
            max_codepoint=0x7E,
        )
        # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\b', r'\f', r'\n', r'\r', r'\t',
        ])
        # Unicode escape \uXXXX with hex digits
        hex_digit = st.sampled_from("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: "".join(t))

        # Mix safe chars and escapes/unicode escapes
        # To keep it simple, generate a list of length 0..20 of either safe char or escape
        char_or_escape = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        content = st.lists(char_or_escape, max_size=20).map("".join)
        return content.map(lambda s: f'"{s}"')

    # NUMBER strategy: generate valid JSON numbers as strings
    def json_number():
        # Use Hypothesis floats but convert to JSON number string format
        # To keep it simple, generate integers and floats with optional exponent
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        frac_part = st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)
            .map(lambda f: f"{f:.6f}".lstrip("0"))
            .filter(lambda s: s.startswith("."))
        )
        exp_part = st.one_of(
            st.just(""),
            st.integers(min_value=-100, max_value=100).map(lambda e: f"e{e}" if e >= 0 else f"e{e}")
        )
        sign = st.one_of(st.just(""), st.just("-"))
        return st.tuples(sign, int_part, frac_part, exp_part).map(lambda t: "".join(t))

    # Forward declarations for recursive structures
    # We'll define value recursively below

    # Compose value strategy recursively
    def json_value():
        # We'll define recursive strategy here
        # Use st.recursive to build obj and arr from primitives
        json_primitive = st.one_of(
            json_string(),
            json_number(),
            json_null,
            json_true,
            json_false,
        )

        # obj: { pair (, pair)* } or {}
        # pair: STRING : value
        # arr: [ value (, value)* ] or []

        # pair strategy
        def pair():
            return st.tuples(json_string(), st.just(":"), value).map(lambda t: t[0] + t[1] + t[2])

        # obj strategy
        def obj():
            # pairs separated by commas
            pairs = st.lists(pair(), max_size=5)
            return pairs.map(lambda ps: "{" + (",".join(ps) if ps else "") + "}")

        # arr strategy
        def arr():
            values = st.lists(value, max_size=5)
            return values.map(lambda vs: "[" + (",".join(vs) if vs else "") + "]")

        # Recursive value strategy
        return st.recursive(
            json_primitive,
            lambda children: st.one_of(obj(), arr()),
            max_leaves=10,
        )

    value = json_value()

    # Compose full JSON text: value + EOF
    json_text = value.map(lambda s: s)

    s = draw(json_text)
    return s.encode("utf-8")