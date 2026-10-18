from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes
    def json_string():
        # Characters allowed inside JSON strings excluding control chars and quotes/backslash
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \uXXXX
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))

        # Either safe char, escape sequence, or unicode escape
        json_char = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape,
        )

        # Build string content with length 0..20
        content = st.lists(json_char, max_size=20).map(''.join)
        return content.map(lambda s: f'"{s}"')

    # NUMBER strategy: produce valid JSON numbers as strings
    def json_number():
        # Use Hypothesis floats converted to JSON number strings, but restrict to finite numbers
        # To keep it simple, generate strings matching the NUMBER grammar
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        frac_part = st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)
              .map(lambda f: f"{f:.6f}".split('.')[1].rstrip('0'))
              .filter(lambda s: s != "")
              .map(lambda s: "." + s)
        )
        exp_part = st.one_of(
            st.just(""),
            st.integers(min_value=-10, max_value=10).map(lambda e: f"e{e}" if e >= 0 else f"e{e}")
        )
        sign = st.one_of(st.just(""), st.just("-"))
        return st.tuples(sign, int_part, frac_part, exp_part).map(lambda t: ''.join(t))

    # Recursive value strategy
    def json_value():
        # Forward declaration for recursion
        return st.recursive(
            base=st.one_of(
                json_string(),
                json_number(),
                json_true,
                json_false,
                json_null,
            ),
            extend=lambda children: st.one_of(
                # Object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string(),
                    values=children,
                    max_size=3,
                    # To keep keys valid JSON strings, keys are already quoted strings
                ).map(lambda d: "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"),
                # Array: [ value (, value)* ] or []
                st.lists(children, max_size=3).map(lambda l: "[" + ",".join(l) + "]"),
            ),
            max_leaves=10,
        )

    val = draw(json_value())
    return val.encode("utf-8")