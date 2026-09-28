from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.from_regex(
        r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?",
        fullmatch=True,
    )
    # STRING: roughly valid JSON strings with escapes and safe codepoints
    # We'll generate strings with safe unicode codepoints and some escapes
    def json_string():
        # safe codepoints: exclude control chars and quotes/backslash
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t',
        ])
        # unicode escape \uXXXX with hex digits
        hex_digit = st.sampled_from("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: "".join(t))
        # Compose string content from safe chars and escapes
        content = st.lists(
            st.one_of(
                safe_chars.map(lambda c: c),
                escapes,
                unicode_escape,
            ),
            min_size=0,
            max_size=20,
        ).map("".join)
        return content.map(lambda s: f'"{s}"')

    json_string = json_string()

    # Recursive definitions for arrays and objects
    # Use st.recursive to keep bounded size and depth
    def json_value():
        base = st.one_of(
            json_string,
            json_number,
            json_true,
            json_false,
            json_null,
        )
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: {} or {"pair", ...}
                st.builds(
                    lambda pairs: "{" + ",".join(pairs) + "}",
                    st.lists(
                        st.tuples(json_string, children).map(lambda t: f"{t[0]}:{t[1]}"),
                        max_size=3,
                    ),
                ),
                # empty object
                st.just("{}"),
                # array: [] or [value, ...]
                st.builds(
                    lambda values: "[" + ",".join(values) + "]",
                    st.lists(children, max_size=3),
                ),
                # empty array
                st.just("[]"),
            ),
            max_leaves=10,
        )

    result = draw(json_value())
    return result.encode("utf-8")