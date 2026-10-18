from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: simplified safe string with escapes
    def json_string():
        # Use a limited set of safe characters plus escapes
        # SAFECODEPOINT excludes control chars and " \, so we use ascii_letters + digits + some punctuation
        safe_chars = st.characters(
            blacklist_characters='"\\',
            blacklist_categories=('Cc',),  # control chars
            min_codepoint=0x20,
            max_codepoint=0x7E,
        )
        # To keep it simple, generate strings with safe chars and some escapes
        # We'll allow backslash escapes for \", \\, \b, \f, \n, \r, \t
        # Compose string from safe chars and escaped sequences
        escape_sequences = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Compose a string of length 0..20 with a mix of safe chars and escapes
        pieces = st.lists(st.one_of(safe_chars.map(lambda c: c), escape_sequences), max_size=20)
        s = draw(pieces)
        # Join and wrap in quotes
        return '"' + ''.join(s) + '"'

    # NUMBER: use Hypothesis floats and ints, then format as JSON number string
    def json_number():
        # Generate numbers that fit JSON number grammar
        # Use floats and ints, exclude NaN and inf
        n = draw(
            st.one_of(
                st.integers(min_value=-10**6, max_value=10**6),
                st.floats(min_value=-1e6, max_value=1e6, allow_infinity=False, allow_nan=False),
            )
        )
        # Format number as JSON number string
        # Use repr for floats, str for ints
        if isinstance(n, int):
            return str(n)
        else:
            # Format float with minimal representation, avoid trailing .0 if possible
            s = repr(n)
            # repr may produce scientific notation, which is valid JSON number
            return s

    # Recursive value strategy
    def json_value():
        # Base cases: string, number, true, false, null
        base = st.one_of(
            json_string(),
            st.builds(lambda x: x, json_number()),
            json_true,
            json_false,
            json_null,
        )
        # Recursive cases: object and array
        # Use st.recursive to keep size bounded
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.builds(
                    lambda pairs: "{" + ",".join(pairs) + "}",
                    st.lists(
                        st.tuples(json_string(), children),
                        max_size=3,
                    ).map(lambda pairs: [f"{k}:{v}" for k, v in pairs]),
                ),
                # array: [ value (, value)* ] or []
                st.builds(
                    lambda values: "[" + ",".join(values) + "]",
                    st.lists(children, max_size=3),
                ),
            ),
            max_leaves=10,
        )

    # Compose full JSON text with EOF (just ensure full string)
    json_text = draw(json_value())
    return json_text.encode("utf-8")