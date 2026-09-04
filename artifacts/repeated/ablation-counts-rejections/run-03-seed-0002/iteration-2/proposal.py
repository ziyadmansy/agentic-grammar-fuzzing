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
    # JSON string with safe codepoints and escapes
    # We'll build strings from characters excluding control chars and quotes/backslash,
    # plus some escapes.
    # To keep it simple, use Hypothesis text with whitelist of safe characters and
    # add some escapes manually.
    safe_chars = (
        st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',),
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
    )
    # Escape sequences allowed: \" \\ \/ \b \f \n \r \t and \uXXXX
    # We'll add some escapes by mixing safe chars and escape sequences.
    # Compose a string strategy that sometimes inserts escapes.
    def json_string_chars():
        escapes = st.sampled_from(
            ['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']
        )
        # Unicode escapes \uXXXX with hex digits
        hex_digit = st.sampled_from("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just("\\u"),
            hex_digit,
            hex_digit,
            hex_digit,
            hex_digit,
        ).map(lambda t: "".join(t))
        return st.one_of(safe_chars.map(lambda c: c), escapes, unicode_escape)

    # Compose string of length 0..20 chars
    json_string = st.lists(json_string_chars(), max_size=20).map(lambda chars: '"' + "".join(chars) + '"')

    # Recursive JSON value definition
    # We'll limit max depth to avoid huge recursion and output
    # Use st.recursive with max_leaves=10 to keep size bounded

    base = st.one_of(json_string, json_number, json_null, json_true, json_false)

    def extend_json(value_strat):
        # object: { pair (, pair)* } or {}
        # pair: STRING : value
        pair = st.tuples(json_string, value_strat).map(lambda p: f"{p[0]}:{p[1]}")
        obj = st.lists(pair, max_size=5).map(
            lambda pairs: "{" + (",".join(pairs) if pairs else "") + "}"
        )
        # array: [ value (, value)* ] or []
        arr = st.lists(value_strat, max_size=5).map(
            lambda values: "[" + (",".join(values) if values else "") + "]"
        )
        return st.one_of(obj, arr)

    json_value = st.recursive(base, extend_json, max_leaves=10)

    s = draw(json_value)
    return s.encode("utf-8")