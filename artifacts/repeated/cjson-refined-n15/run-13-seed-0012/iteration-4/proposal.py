from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string strategy: produce valid JSON strings with escapes and safe codepoints
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \uXXXX
        hex_digit = st.characters(min_codepoint=0x30, max_codepoint=0x39).filter(lambda c: c in "0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just('\\u'),
            st.sampled_from('0123456789abcdefABCDEF'),
            st.sampled_from('0123456789abcdefABCDEF'),
            st.sampled_from('0123456789abcdefABCDEF'),
            st.sampled_from('0123456789abcdefABCDEF'),
        ).map(lambda t: ''.join(t))

        # Mix safe chars and escapes/unicode escapes
        char_piece = st.one_of(
            safe_char.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Build string pieces of length 0 to 20 (bounded)
        pieces = st.lists(char_piece, max_size=20)
        return pieces.map(lambda chars: '"' + ''.join(chars) + '"')

    json_string_st = json_string()

    # JSON number strategy
    # Use Hypothesis built-in floats but convert to JSON number format strings
    def json_number():
        # Generate numbers as strings matching the grammar
        # We'll generate integers and floats with optional exponent
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        frac_part = st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False).map(
                lambda f: ("%.10f" % f).lstrip("0") if f != 0 else ""
            )
        )
        # Instead of floats, build fractional parts manually
        frac_digits = st.text(min_size=1, max_size=10, alphabet=st.characters(min_codepoint=48, max_codepoint=57))
        frac = st.one_of(st.just(""), frac_digits.map(lambda d: "." + d))
        # Exponent part
        exp = st.one_of(
            st.just(""),
            st.tuples(
                st.sampled_from(["e", "E"]),
                st.sampled_from(["+", "-", ""]),
                st.integers(min_value=0, max_value=100).map(str)
            ).map(lambda t: t[0] + t[1] + t[2])
        )
        # Optional minus
        sign = st.one_of(st.just(""), st.just("-"))
        return st.tuples(sign, int_part, frac, exp).map(lambda t: "".join(t))

    json_number_st = json_number()

    # Recursive JSON value strategy
    # Use recursive to build nested arrays and objects with bounded depth and size
    def json_value():
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_true,
            json_false,
            json_null,
        )

        # Forward declare for recursion
        return st.recursive(
            base,
            lambda children: st.one_of(
                # Array: [value, value, ...] or []
                st.lists(children, max_size=5).map(
                    lambda vs: "[" + ",".join(vs) + "]"
                ),
                # Object: {"string": value, ...} or {}
                st.dictionaries(
                    json_string_st.map(lambda s: s[1:-1]),  # strip quotes for keys
                    children,
                    max_size=5
                ).map(
                    lambda d: "{" + ",".join(f'"{k}":{v}' for k, v in d.items()) + "}"
                ),
            ),
            max_leaves=10,
        )

    json_str = draw(json_value())
    return json_str.encode("utf-8")