from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    def json_string():
        # Characters allowed inside strings (excluding control chars and " \)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \uXXXX
        hex_digit = st.characters(min_codepoint=0x30, max_codepoint=0x39).filter(lambda c: c in '0123456789abcdefABCDEF')
        unicode_escape = st.tuples(
            st.just('\\u'),
            st.text('0123456789abcdefABCDEF', min_size=4, max_size=4)
        ).map(lambda t: ''.join(t))
        # Mix safe chars and escapes/unicode escapes
        # To keep it simple, generate a string of length up to 20
        def char_piece():
            return st.one_of(
                safe_char.map(lambda c: c),
                escapes,
                unicode_escape,
            )
        pieces = st.lists(char_piece(), max_size=20)
        s = draw(pieces)
        return '"' + ''.join(s) + '"'

    json_string_st = st.deferred(lambda: json_string())

    # NUMBER strategy: produce valid JSON numbers
    def json_number():
        # Use Hypothesis built-in floats converted to JSON number strings
        # but restrict to finite numbers and avoid exponent overflow
        # We'll generate strings matching the grammar instead
        int_part = st.one_of(
            st.just("0"),
            st.tuples(st.characters(min_codepoint=49, max_codepoint=57), st.text('0123456789', max_size=5)).map(lambda t: t[0] + t[1])
        )
        frac_part = st.one_of(st.just(""), st.tuples(st.just("."), st.text('0123456789', min_size=1, max_size=5)).map(lambda t: t[0] + t[1]))
        exp_part = st.one_of(
            st.just(""),
            st.tuples(
                st.sampled_from(["e", "E"]),
                st.sampled_from(["+", "-", ""]),
                st.text('0123456789', min_size=1, max_size=3)
            ).map(lambda t: t[0] + t[1] + t[2])
        )
        sign = st.one_of(st.just(""), st.just("-"))
        return st.tuples(sign, int_part, frac_part, exp_part).map(lambda t: ''.join(t))

    json_number_st = st.deferred(lambda: json_number())

    # Recursive value strategy
    # We'll use st.recursive to build obj and arr with bounded depth and size
    def json_value():
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_null,
            json_true,
            json_false,
        )
        # obj and arr will be defined recursively below
        return st.deferred(lambda: st.recursive(
            base,
            lambda children: st.one_of(
                # obj: {} or {"pair", ...}
                st.builds(
                    lambda pairs: "{" + ",".join(pairs) + "}",
                    st.lists(
                        st.tuples(json_string_st, children),
                        max_size=3
                    ).map(lambda pairs: [k + ":" + v for k, v in pairs])
                ),
                # arr: [] or [value, ...]
                st.builds(
                    lambda values: "[" + ",".join(values) + "]",
                    st.lists(children, max_size=3)
                )
            ),
            max_leaves=10
        ))

    val = draw(json_value())
    return val.encode('utf-8')