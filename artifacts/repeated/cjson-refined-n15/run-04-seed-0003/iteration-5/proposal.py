from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives as strings
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then json.dumps them to ensure correctness.
    # But since we cannot import json or eval, we must generate strings manually.
    # Instead, generate strings with safe characters and escapes.
    # We'll generate strings of safe unicode codepoints excluding control chars and quotes/backslash.
    # Then add escapes for quotes and backslash.

    # Define safe characters for JSON strings (excluding control chars, quote, backslash)
    safe_chars = st.characters(
        blacklist_characters=['"', '\\'],
        blacklist_categories=('Cc',)  # control chars
    )

    # Escaped characters: \", \\, \b, \f, \n, \r, \t
    escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])

    # Compose string pieces: either safe char or escape sequence
    string_piece = st.one_of(
        safe_chars.map(lambda c: c),
        escapes
    )

    # Generate string pieces list of length 0 to 20 (bounded)
    string_pieces = st.lists(string_piece, max_size=20)

    @st.composite
    def json_string(draw):
        pieces = draw(string_pieces)
        s = ''.join(pieces)
        return '"' + s + '"'

    # NUMBER: generate valid JSON numbers as strings
    # Use Hypothesis number generation and convert to JSON number string
    @st.composite
    def json_number(draw):
        # Generate float or int within reasonable bounds
        # Avoid inf, nan
        n = draw(st.one_of(
            st.integers(min_value=-10**6, max_value=10**6),
            st.floats(min_value=-10**6, max_value=10**6, allow_infinity=False, allow_nan=False)
        ))
        # Format as JSON number string
        if isinstance(n, int):
            return str(n)
        else:
            # Use repr to get a JSON-compatible float string (e.g. "1.23", "0.0", "-0.5")
            # repr of float is valid JSON number format
            return repr(n)

    # Recursive JSON value strategy producing strings of JSON text
    def json_value():
        # Base cases: string, number, true, false, null
        base = st.one_of(
            json_string(),
            json_number(),
            json_true,
            json_false,
            json_null,
        )

        # Recursive cases: object and array
        # Use bounded recursion depth and size
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.builds(
                    lambda pairs: '{' + ','.join(pairs) + '}',
                    st.lists(
                        st.tuples(
                            json_string(),
                            children
                        ).map(lambda t: t[0] + ':' + t[1]),
                        max_size=3
                    )
                ),
                # array: [ value (, value)* ] or []
                st.builds(
                    lambda elements: '[' + ','.join(elements) + ']',
                    st.lists(children, max_size=3)
                )
            ),
            max_leaves=10
        )

    s = draw(json_value())
    return s.encode('utf-8')