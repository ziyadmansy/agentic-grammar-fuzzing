from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # STRING: roughly matching JSON string with escapes and safe codepoints
    # We'll generate Python strings and then json-encode them to ensure correctness.
    # But since we cannot import json or eval, we build a safe string strategy:
    # Use characters excluding control chars and backslash and quote, plus some escapes.
    # To keep it simple, generate unicode strings with safe codepoints and then quote them.
    # We'll generate strings and then quote them manually.
    def json_string(s: str) -> str:
        # Escape backslash and quote and control chars
        def esc_char(c):
            if c == '"':
                return r'\"'
            if c == '\\':
                return r'\\'
            if c == '\b':
                return r'\b'
            if c == '\f':
                return r'\f'
            if c == '\n':
                return r'\n'
            if c == '\r':
                return r'\r'
            if c == '\t':
                return r'\t'
            # Control chars escaped as \uXXXX
            if ord(c) < 0x20:
                return '\\u%04x' % ord(c)
            return c
        return '"' + ''.join(esc_char(c) for c in s) + '"'

    json_string_chars = st.characters(
        blacklist_characters=['"', '\\'],
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    )
    json_string_strat = st.text(json_string_chars, max_size=20).map(json_string)

    # Recursive strategy for JSON values
    # We'll use st.recursive with base cases and composite containers

    base = st.one_of(json_null, json_true, json_false, json_number, json_string_strat)

    # To keep size bounded, limit max depth and max container size
    max_depth = 3
    max_size = 4

    def json_obj_strat(children):
        # pair: STRING ':' value
        pair = st.tuples(json_string_strat, children).map(lambda p: p[0] + ':' + p[1])
        pairs = st.lists(pair, max_size=max_size)
        # either empty object or object with pairs separated by commas
        return st.one_of(
            st.just('{}'),
            pairs.map(lambda ps: '{' + ','.join(ps) + '}')
        )

    def json_arr_strat(children):
        # list of values separated by commas or empty array
        arrs = st.lists(children, max_size=max_size)
        return st.one_of(
            st.just('[]'),
            arrs.map(lambda vs: '[' + ','.join(vs) + ']')
        )

    json_value = st.recursive(
        base,
        lambda children: st.one_of(
            json_obj_strat(children),
            json_arr_strat(children),
        ),
        max_leaves=100,
    )

    s = draw(json_value)
    return s.encode('utf-8')