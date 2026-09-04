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
    # STRING: roughly valid JSON strings with escapes and safe codepoints
    # We'll generate unicode strings and then escape them properly
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        # We'll generate unicode strings and then escape them
        # To keep it simple, generate ascii printable except backslash and quote, plus some escapes
        safe_chars = st.characters(
            blacklist_characters=['\\', '"', '\u0000', '\u0001', '\u0002', '\u0003', '\u0004', '\u0005',
                                  '\u0006', '\u0007', '\u0008', '\u000b', '\u000c', '\u000e', '\u000f',
                                  '\u0010', '\u0011', '\u0012', '\u0013', '\u0014', '\u0015', '\u0016',
                                  '\u0017', '\u0018', '\u0019', '\u001a', '\u001b', '\u001c', '\u001d',
                                  '\u001e', '\u001f', '"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x7E,
        )
        # Generate a string with length up to 20
        base_str = st.text(safe_chars, max_size=20)

        # Add some escapes randomly
        escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Compose a string with some escapes inserted randomly
        @st.composite
        def escaped_string(draw):
            s = draw(base_str)
            # Insert 0 to 3 escapes at random positions
            n_escapes = draw(st.integers(0, 3))
            for _ in range(n_escapes):
                pos = draw(st.integers(0, len(s)))
                esc = draw(escapes)
                s = s[:pos] + esc + s[pos:]
            return s

        return escaped_string().map(lambda s: f'"{s}"')

    json_string = json_string()

    # Recursive definition for arrays and objects
    # We'll limit max depth to 3 and max size to keep output bounded

    # Forward declaration for value
    # Use recursive strategy to generate nested arrays and objects
    def json_value():
        # Base values
        base = st.one_of(
            json_string,
            json_number,
            json_true,
            json_false,
            json_null,
        )

        # Recursive containers
        # Use st.recursive to build nested arrays and objects
        def extend(inner):
            # pair: STRING ':' value
            pair = st.tuples(json_string, inner).map(lambda t: f"{t[0]}:{t[1]}")

            obj = st.builds(
                lambda pairs: "{" + ",".join(pairs) + "}",
                st.lists(pair, max_size=3),
            )

            arr = st.builds(
                lambda vals: "[" + ",".join(vals) + "]",
                st.lists(inner, max_size=3),
            )

            return st.one_of(obj, arr)

        return st.recursive(base, extend, max_leaves=10)

    json_val = json_value()

    # Compose full JSON with EOF (just ensure full string)
    json_full = json_val.map(lambda s: s)

    s = draw(json_full)
    return s.encode("utf-8")