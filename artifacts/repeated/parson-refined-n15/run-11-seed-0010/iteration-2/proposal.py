from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # JSON strings: use Hypothesis text with safe codepoints, escape quotes and backslashes
    def json_string():
        # Use safe unicode codepoints excluding control chars and quotes/backslash
        # SAFECODEPOINT ~["\\\u0000-\u001F]
        # We'll generate text excluding control chars and quotes/backslash, then escape
        def escape_json_string(s: str) -> str:
            # Escape backslash and quotes, and control chars if any
            def esc_char(c):
                if c == '"':
                    return '\\"'
                elif c == '\\':
                    return '\\\\'
                elif c == '\b':
                    return '\\b'
                elif c == '\f':
                    return '\\f'
                elif c == '\n':
                    return '\\n'
                elif c == '\r':
                    return '\\r'
                elif c == '\t':
                    return '\\t'
                elif ord(c) < 0x20:
                    # Unicode escape for control chars
                    return '\\u%04x' % ord(c)
                else:
                    return c
            return '"' + ''.join(esc_char(c) for c in s) + '"'

        # Generate text excluding control chars and quotes/backslash
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        s = draw(st.text(safe_chars, max_size=20))
        return escape_json_string(s)

    json_string_st = st.deferred(json_string)

    # Recursive JSON value strategy
    def json_value():
        # Compose all possible JSON values
        # We'll use recursive to bound size and depth
        base = st.one_of(
            json_string_st,
            json_number,
            json_null,
            json_true,
            json_false,
        )

        # Recursive containers: objects and arrays
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.builds(
                    lambda pairs: "{" + ",".join(pairs) + "}",
                    st.lists(
                        st.tuples(
                            json_string_st,
                            children,
                        ).map(lambda kv: kv[0] + ":" + kv[1]),
                        max_size=4,
                    ),
                ),
                # array: [ value (, value)* ] or []
                st.builds(
                    lambda values: "[" + ",".join(values) + "]",
                    st.lists(children, max_size=4),
                ),
            ),
            max_leaves=10,
        )

    # Compose full JSON text with EOF
    json_text = json_value()

    s = draw(json_text)
    return s.encode("utf-8")