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
    # STRING: roughly matching the grammar, allowing escapes and safe codepoints
    # We'll generate Python strings and then JSON-encode them to ensure correctness.
    # But since we want bytes output, we'll generate Python strings and then dump them.
    # To keep near-valid cases, we allow some invalid escapes by manual construction.
    # However, Hypothesis's json module can generate valid JSON strings, but we want control.
    # We'll generate strings with safe unicode codepoints and some escapes.
    def json_string():
        # Characters allowed: safe codepoints (excluding control chars and quotes/backslash)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'] + [chr(c) for c in range(0x00, 0x20)]
        )
        # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        # We'll generate strings with a mix of safe chars and escapes.
        # To keep it simple, generate a list of either safe chars or escapes.
        escapes = st.sampled_from([
            r'\"', r'\\', r'\b', r'\f', r'\n', r'\r', r'\t',
            # Unicode escape with 4 hex digits
            lambda: r'\u' + ''.join(draw(st.sampled_from('0123456789abcdefABCDEF')) for _ in range(4))
        ])
        # Compose a string of length up to 20 with safe chars or escapes
        def piece():
            # 80% safe char, 20% escape
            return st.one_of(
                safe_chars.map(lambda c: c),
                st.deferred(lambda: st.just(draw(escapes)() if callable(draw(escapes)) else draw(escapes)))
            )
        pieces = st.lists(piece(), max_size=20)
        s = draw(pieces)
        # Join pieces into a string, then wrap in quotes
        return '"' + ''.join(s) + '"'

    json_string_st = st.deferred(json_string)

    # Recursive JSON value generator
    def json_value():
        # Use recursive to bound size and depth
        base = st.one_of(
            json_string_st,
            json_number,
            json_true,
            json_false,
            json_null,
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
                        ).map(lambda t: f"{t[0]}:{t[1]}"),
                        max_size=3,
                    ),
                ),
                # empty object
                st.just("{}"),
                # array: [ value (, value)* ] or []
                st.builds(
                    lambda vals: "[" + ",".join(vals) + "]",
                    st.lists(children, max_size=3),
                ),
                # empty array
                st.just("[]"),
            ),
            max_leaves=10,
        )

    val = draw(json_value())
    # Return as bytes
    return val.encode("utf-8")