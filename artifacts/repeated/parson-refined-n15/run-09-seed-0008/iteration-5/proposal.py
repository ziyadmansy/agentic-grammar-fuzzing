from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \uXXXX
        hex_digit = st.characters('0123456789abcdefABCDEF')
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))
        escape_seq = st.one_of(escapes, unicode_escape)

        # Mix safe chars and escapes
        char = st.one_of(safe_chars.map(lambda c: c), escape_seq)
        # Build string of length 0..20 (bounded)
        content = st.lists(char, max_size=20).map(''.join)
        return content.map(lambda s: f'"{s}"')

    # NUMBER strategy: produce valid JSON numbers
    def json_number():
        # Use Hypothesis built-in floats, but convert to JSON number string
        # Limit range and precision to keep output short and valid
        # We'll generate strings matching the grammar instead of floats directly
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        frac_part = st.one_of(st.just(""), st.floats(min_value=0, max_value=1).map(lambda f: f"{f:.6f}".lstrip("0")))
        # frac_part above can produce strings like ".123456"
        # But to keep grammar strict, we build fractional part as '.' + digits
        frac_digits = st.text(st.characters("0123456789"), min_size=1, max_size=6)
        frac = st.one_of(st.just(""), frac_digits.map(lambda d: "." + d))
        exp_sign = st.one_of(st.just(""), st.sampled_from(["+", "-"]))
        exp_digits = st.text(st.characters("0123456789"), min_size=1, max_size=4)
        exp = st.one_of(st.just(""), exp_digits.map(lambda d: "e" + d), exp_digits.map(lambda d: "e+" + d), exp_digits.map(lambda d: "e-" + d))
        # Combine all parts
        def build_number(t):
            sign, intp, fracp, expp = t
            return f"{sign}{intp}{fracp}{expp}"
        sign = st.one_of(st.just(""), st.just("-"))
        return st.tuples(sign, int_part, frac, exp).map(build_number)

    # Recursive value strategy
    def json_value():
        # Use recursive to build nested objects and arrays
        base = st.one_of(
            json_string(),
            json_number(),
            json_null,
            json_true,
            json_false,
        )

        # Forward declare obj and arr to use in recursive
        # We'll define them inside recursive call below

        def json_obj():
            # pair: STRING ':' value
            # Use small number of pairs to keep size bounded
            def pair():
                return st.tuples(json_string(), json_value()).map(lambda t: f"{t[0]}:{t[1]}")

            pairs = st.lists(pair(), max_size=5)
            return pairs.map(lambda ps: "{" + ",".join(ps) + "}" if ps else "{}")

        def json_arr():
            # array of values, max 5 elements
            vals = st.lists(json_value(), max_size=5)
            return vals.map(lambda vs: "[" + ",".join(vs) + "]" if vs else "[]")

        return st.recursive(
            base,
            lambda children: st.one_of(json_obj(), json_arr()),
            max_leaves=10,
        )

    # Compose full JSON with EOF
    json_str = json_value()
    s = draw(json_str)
    return s.encode("utf-8")