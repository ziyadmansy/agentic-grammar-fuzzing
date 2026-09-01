from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.from_regex(
        r'-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?',
        fullmatch=True,
    )
    # STRING: roughly valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode with json.dumps style quotes and escapes.
    # To keep it simple, generate unicode strings excluding control chars and quotes/backslash,
    # plus some escapes.
    # We'll generate strings with some escapes manually.
    def json_string():
        # safe chars: exclude control chars, quotes, backslash
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # escape sequences: \", \\, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\b', r'\f', r'\n', r'\r', r'\t',
        ])
        # unicode escape \uXXXX with hex digits
        def unicode_escape():
            hex_digits = st.sampled_from('0123456789abcdefABCDEF')
            return st.tuples(hex_digits, hex_digits, hex_digits, hex_digits).map(
                lambda t: r'\u' + ''.join(t)
            )
        escape_seq = st.one_of(escapes, unicode_escape())

        # Build a string with mix of safe chars and escapes
        # We'll generate a list of length 0..10 of either safe char or escape seq
        chunk = st.one_of(
            safe_chars.map(lambda c: c),
            escape_seq,
        )
        pieces = st.lists(chunk, max_size=10)
        return pieces.map(lambda pieces: '"' + ''.join(pieces) + '"')

    json_string_st = json_string()

    # Recursive JSON value
    # Use st.recursive to build obj and arr
    base = st.one_of(
        json_string_st,
        json_number,
        json_true,
        json_false,
        json_null,
    )

    # Forward declarations for obj and arr
    # We'll define them inside a function to use draw

    def json_value():
        # Use recursive to build nested structures, bounded max size
        return st.recursive(
            base,
            lambda children: st.one_of(
                # obj: { pair (, pair)* } or {}
                st.builds(
                    lambda pairs: "{" + ",".join(pairs) + "}" if pairs else "{}",
                    st.lists(
                        st.tuples(
                            json_string_st,
                            children,
                        ).map(lambda t: f"{t[0]}:{t[1]}"),
                        max_size=3,
                    ),
                ),
                # arr: [ value (, value)* ] or []
                st.builds(
                    lambda values: "[" + ",".join(values) + "]" if values else "[]",
                    st.lists(children, max_size=3),
                ),
            ),
            max_leaves=10,
        )

    val = draw(json_value())
    # Add EOF by definition (whole string)
    return val.encode("utf-8")