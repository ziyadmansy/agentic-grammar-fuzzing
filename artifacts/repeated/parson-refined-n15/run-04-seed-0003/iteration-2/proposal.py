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
    # JSON string with escapes and safe codepoints, roughly matching grammar
    # Use a simplified safe string strategy with some escapes
    def json_string():
        # Characters allowed inside strings (excluding control chars and " \)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t'
        ])
        # Unicode escape \uXXXX with hex digits
        unicode_escape = st.builds(
            lambda h1,h2,h3,h4: r"\u" + h1 + h2 + h3 + h4,
            st.sampled_from("0123456789abcdefABCDEF"),
            st.sampled_from("0123456789abcdefABCDEF"),
            st.sampled_from("0123456789abcdefABCDEF"),
            st.sampled_from("0123456789abcdefABCDEF"),
        )
        # Mix safe chars and escapes/unicode escapes
        char_piece = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Build string of length 0 to 20 (bounded)
        pieces = st.lists(char_piece, max_size=20)
        return pieces.map(lambda chars: '"' + "".join(chars) + '"')

    json_str = json_string()

    # Recursive JSON value
    # Use st.recursive to build nested objects and arrays with bounded depth and size
    base = st.one_of(json_null, json_true, json_false, json_number, json_str)

    def json_obj():
        # pair: STRING ':' value
        pair = st.tuples(json_str, generated_json_value).map(lambda p: f"{p[0]}:{p[1]}")
        # object: '{' pair (',' pair)* '}' or '{}'
        # limit pairs to max 5 to keep size bounded
        pairs = st.lists(pair, max_size=5)
        return pairs.map(lambda ps: "{" + ",".join(ps) + "}" if ps else "{}")

    def json_arr():
        # array: '[' value (',' value)* ']' or '[]'
        # limit elements to max 5
        elems = st.lists(generated_json_value, max_size=5)
        return elems.map(lambda es: "[" + ",".join(es) + "]" if es else "[]")

    # We need to define generated_json_value to use in json_obj and json_arr
    # Use st.recursive with base and containers
    generated_json_value = st.recursive(
        base,
        lambda children: st.one_of(json_obj(), json_arr()),
        max_leaves=10,
    )

    # Draw a JSON value and encode as bytes
    val = draw(generated_json_value)
    return val.encode("utf-8")