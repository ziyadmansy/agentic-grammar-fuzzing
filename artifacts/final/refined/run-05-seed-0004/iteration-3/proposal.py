from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_bool = st.one_of(json_true, json_false)
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, '.15g'))
    # JSON string with safe codepoints and escapes
    # We generate Python strings and then JSON-encode them with escapes
    def json_string(s: str) -> str:
        # Escape backslash, quotes, and control chars
        def esc_char(c):
            if c == '"':
                return r'\"'
            elif c == '\\':
                return r'\\'
            elif c == '\b':
                return r'\b'
            elif c == '\f':
                return r'\f'
            elif c == '\n':
                return r'\n'
            elif c == '\r':
                return r'\r'
            elif c == '\t':
                return r'\t'
            elif ord(c) < 0x20:
                return '\\u%04x' % ord(c)
            else:
                return c
        return '"' + ''.join(esc_char(c) for c in s) + '"'
    json_string_strat = st.text(
        alphabet=st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=20,
    ).map(json_string)

    # Recursive JSON value strategy
    # We limit max_leaves to keep sizes bounded
    json_value = st.deferred(lambda: json_value_inner)

    json_pair = st.tuples(json_string_strat, json_value).map(lambda p: p[0] + ':' + p[1])

    json_obj = st.recursive(
        st.just('{}'),
        lambda children: st.builds(
            lambda pairs: '{' + ','.join(pairs) + '}',
            st.lists(json_pair, min_size=1, max_size=4),
        ),
        max_leaves=10,
    )

    json_arr = st.recursive(
        st.just('[]'),
        lambda children: st.builds(
            lambda values: '[' + ','.join(values) + ']',
            st.lists(json_value, min_size=1, max_size=4),
        ),
        max_leaves=10,
    )

    json_value_inner = st.one_of(
        json_string_strat,
        json_number,
        json_obj,
        json_arr,
        json_true,
        json_false,
        json_null,
    )

    # Draw a full JSON value and encode as bytes
    s = draw(json_value)
    return s.encode('utf-8')