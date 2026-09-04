from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # JSON strings: roughly matching grammar STRING (no control chars, escapes)
    # We'll allow some escapes to preserve near-valid cases
    def json_string():
        # safe codepoints excluding control chars and quotes/backslash
        safe_char = st.characters(
            blacklist_characters='"\\',
            blacklist_categories=('Cc',),
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # escape sequences roughly matching ESC
        escape_seq = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t',
        ])
        # unicode escape \uXXXX
        hex_digit = st.sampled_from("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: "".join(t))
        char_or_escape = st.one_of(safe_char.map(lambda c: c), escape_seq, unicode_escape)
        # string length bounded to keep size reasonable
        return st.lists(char_or_escape, min_size=0, max_size=20).map(lambda cs: '"' + "".join(cs) + '"')

    json_string_st = json_string()

    # Forward declaration for recursive structures
    # We'll use st.recursive to build obj and arr

    # Pair: STRING ':' value
    @st.composite
    def pair(draw, value_st):
        k = draw(json_string_st)
        v = draw(value_st)
        return f"{k}:{v}"

    # Recursive value strategy
    def json_value():
        base = st.one_of(
            json_string_st,
            json_number,
            json_true,
            json_false,
            json_null,
        )
        # recursive containers
        def extend(value_st):
            obj_st = st.lists(pair(value_st), max_size=5).map(
                lambda pairs: "{" + (",".join(pairs)) + "}" if pairs else "{}"
            )
            arr_st = st.lists(value_st, max_size=5).map(
                lambda vs: "[" + (",".join(vs)) + "]" if vs else "[]"
            )
            return st.one_of(obj_st, arr_st)

        return st.recursive(base, extend, max_leaves=10)

    value_st = json_value()

    # Full JSON: value + EOF
    json_st = value_st.map(lambda s: s)

    s = draw(json_st)
    return s.encode("utf-8")