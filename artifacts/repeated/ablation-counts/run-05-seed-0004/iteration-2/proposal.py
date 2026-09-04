from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, '.15g'))
    # JSON strings with safe codepoints and escapes
    # We'll generate strings that mostly avoid control chars, but allow some escapes
    # to preserve near-valid cases.
    def json_string_chars():
        # safe codepoints excluding control chars and quotes/backslash
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)
        )
        # escape sequences
        escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # unicode escape: \uXXXX
        hex_digit = st.characters('0123456789abcdefABCDEF')
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))
        # combine safe chars and escapes/unicode escapes
        return st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape,
        )
    # Compose string content with length limit to keep size bounded
    json_string_content = st.lists(json_string_chars(), max_size=20).map(''.join)
    json_string = json_string_content.map(lambda s: f'"{s}"')

    # Forward declare value strategy for recursion
    # We'll use st.recursive to build nested objects and arrays
    base = st.one_of(json_string, json_number, json_null, json_true, json_false)

    # Recursive strategy for JSON values
    def json_obj():
        # pair: STRING ':' value
        pair = st.tuples(json_string, st.deferred(lambda: value)).map(lambda t: f'{t[0]}:{t[1]}')
        # object: '{' pair (',' pair)* '}' or '{}'
        # limit pairs to max 3 to keep size bounded
        pairs = st.lists(pair, max_size=3)
        return pairs.map(lambda ps: '{' + ','.join(ps) + '}' if ps else '{}')

    def json_arr():
        # array: '[' value (',' value)* ']' or '[]'
        # limit elements to max 3
        elements = st.lists(st.deferred(lambda: value), max_size=3)
        return elements.map(lambda es: '[' + ','.join(es) + ']' if es else '[]')

    value = st.recursive(
        base,
        lambda children: st.one_of(json_obj(), json_arr()),
        max_leaves=10,
    )

    # Compose full JSON text and encode as bytes
    json_text = value
    s = draw(json_text)
    return s.encode('utf-8')