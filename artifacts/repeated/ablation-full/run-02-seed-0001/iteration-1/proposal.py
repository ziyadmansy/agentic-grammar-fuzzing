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
        max_size=20,
    )
    # STRING: roughly valid JSON strings with escapes and safe codepoints
    # We keep it simple: ASCII printable except control and backslash/quote,
    # plus some escapes.
    def json_string():
        # safe codepoints: exclude control chars and backslash and quote
        safe_chars = st.characters(
            blacklist_characters=['\\', '"'],
            min_codepoint=0x20,
            max_codepoint=0x7E,
        )
        # escape sequences: \", \\, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\b', r'\f', r'\n', r'\r', r'\t',
        ])
        # Unicode escape: \u + 4 hex digits
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: "".join(t))
        # Compose a character as either safe char or escape or unicode escape
        char = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Compose string content length 0..20
        content = st.lists(char, max_size=20).map("".join)
        return content.map(lambda s: f'"{s}"')

    json_string = json_string()

    # Recursive definition for value
    # We use st.recursive to keep size bounded and avoid infinite recursion
    def json_value():
        base = st.one_of(
            json_string,
            json_number,
            json_true,
            json_false,
            json_null,
        )
        # Recursive containers: obj and arr
        # obj: { pair (, pair)* } or {}
        # pair: STRING : value
        def json_pair():
            return st.tuples(json_string, json_value()).map(lambda t: f"{t[0]}:{t[1]}")

        json_obj = st.one_of(
            st.just("{}"),
            st.lists(json_pair(), max_size=5).map(lambda pairs: "{" + ",".join(pairs) + "}"),
        )

        # arr: [ value (, value)* ] or []
        json_arr = st.one_of(
            st.just("[]"),
            st.lists(json_value(), max_size=5).map(lambda values: "[" + ",".join(values) + "]"),
        )

        return st.recursive(
            base,
            lambda children: st.one_of(json_obj, json_arr),
            max_leaves=10,
        )

    result = draw(json_value())
    return result.encode("utf-8")