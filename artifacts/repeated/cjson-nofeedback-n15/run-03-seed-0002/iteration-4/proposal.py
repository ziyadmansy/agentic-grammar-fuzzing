from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and " \)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t'
        ])
        # Unicode escape \uXXXX with hex digits
        hex_digit = st.characters(min_codepoint=0x30, max_codepoint=0x39).filter(lambda c: c in "0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            st.text("0123456789abcdefABCDEF", min_size=4, max_size=4)
        ).map(lambda t: t[0] + t[1])

        # Compose string content from safe chars and escapes
        char_piece = st.one_of(
            safe_char.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Limit length to keep output size bounded
        content = st.text(char_piece, min_size=0, max_size=20)
        return content.map(lambda s: '"' + s + '"')

    json_string_st = json_string()

    # NUMBER strategy: produce valid JSON numbers
    json_number = st.builds(
        lambda sign, int_part, frac, exp: f"{sign}{int_part}{frac}{exp}",
        sign=st.one_of(st.just(""), st.just("-")),
        int_part=st.one_of(st.just("0"), st.integers(min_value=1, max_value=10**6).map(str)),
        frac=st.one_of(st.just(""), st.builds(lambda d: "." + d, st.integers(min_value=0, max_value=10**6).map(str))),
        exp=st.one_of(
            st.just(""),
            st.builds(
                lambda e, s, n: e + s + n,
                st.sampled_from(["e", "E"]),
                st.sampled_from(["", "+", "-"]),
                st.integers(min_value=0, max_value=1000).map(str),
            ),
        ),
    )

    # Recursive value strategy
    def json_value():
        # Forward declaration for recursion
        return st.deferred(lambda: json_value_inner())

    # Compose object and array with recursion bounded by max_leaves
    max_leaves = 5

    def json_object():
        # pair: STRING ':' value
        pair = st.tuples(json_string_st, json_value()).map(lambda t: f"{t[0]}:{t[1]}")
        # object: '{' pair (',' pair)* '}' or '{}'
        return st.lists(pair, max_size=3).map(
            lambda pairs: "{" + ",".join(pairs) + "}" if pairs else "{}"
        )

    def json_array():
        # array: '[' value (',' value)* ']' or '[]'
        return st.lists(json_value(), max_size=3).map(
            lambda values: "[" + ",".join(values) + "]" if values else "[]"
        )

    def json_value_inner():
        # Compose all possible JSON values
        return st.recursive(
            st.one_of(
                json_string_st,
                json_number,
                json_true,
                json_false,
                json_null,
            ),
            lambda children: st.one_of(
                json_object(),
                json_array(),
            ),
            max_leaves=max_leaves,
        )

    # Draw a JSON value and append EOF (nothing) to satisfy grammar json : value EOF
    val = draw(json_value())
    return val.encode("utf-8")