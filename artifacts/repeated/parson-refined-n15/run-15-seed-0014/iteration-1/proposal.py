from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: simple ASCII strings with escapes
    # We'll generate strings with safe codepoints and some escapes
    def json_string():
        # Characters allowed inside strings (excluding control chars and quotes/backslash)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
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
        char = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Generate a string of length 0 to 20 chars
        s = draw(st.lists(char, max_size=20))
        # Join and wrap in quotes
        return '"' + "".join(s) + '"'

    # NUMBER strategy: generate numbers as strings matching grammar
    def json_number():
        # Integer part
        int_part = st.one_of(
            st.just("0"),
            st.tuples(
                st.sampled_from("123456789"),
                st.text(st.digits, max_size=5)
            ).map(lambda t: t[0] + t[1])
        )
        # Fractional part
        frac_part = st.one_of(
            st.just(""),
            st.tuples(
                st.just("."),
                st.text(st.digits, min_size=1, max_size=5)
            ).map(lambda t: t[0] + t[1])
        )
        # Exponent part
        exp_part = st.one_of(
            st.just(""),
            st.tuples(
                st.sampled_from("eE"),
                st.one_of(st.just("+"), st.just("-"), st.just("")),
                st.text(st.digits, min_size=1, max_size=3)
            ).map(lambda t: t[0] + t[1] + t[2])
        )
        # Optional leading minus
        sign = st.one_of(st.just(""), st.just("-"))

        return draw(
            st.tuples(sign, int_part, frac_part, exp_part).map(
                lambda t: "".join(t)
            )
        )

    # Forward declaration for recursive strategy
    # We'll build value recursively with bounded depth
    def json_value():
        # Base values
        base = st.one_of(
            json_string(),
            json_number(),
            json_true,
            json_false,
            json_null,
        )
        # Recursive containers: object and array
        # Use recursive to keep depth bounded
        return st.recursive(
            base,
            lambda children: st.one_of(
                # Object: { pair (, pair)* } or {}
                st.builds(
                    lambda pairs: "{" + ",".join(pairs) + "}",
                    st.lists(
                        st.tuples(json_string(), children).map(lambda p: p[0] + ":" + p[1]),
                        max_size=3
                    )
                ),
                # Array: [ value (, value)* ] or []
                st.builds(
                    lambda values: "[" + ",".join(values) + "]",
                    st.lists(children, max_size=3)
                ),
            ),
            max_leaves=10,
        )

    # Compose full JSON text: value + EOF
    json_text = json_value()

    s = draw(json_text)
    return s.encode("utf-8")