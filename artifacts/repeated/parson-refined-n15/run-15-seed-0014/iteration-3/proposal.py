from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string with escapes and safe codepoints
    # We'll generate unicode strings and then escape them properly
    def json_string():
        # Generate a unicode string without control chars or quotes/backslash
        # We'll allow some escapes by including backslash and quotes and escaping them
        # but to keep it simple, generate normal unicode and then escape
        # Hypothesis has st.text with blacklist characters
        # SAFECODEPOINT excludes control chars and " and \, so exclude those
        safe_chars = (
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # Generate strings up to length 20 to keep size bounded
        s = draw(st.text(safe_chars, max_size=20))
        # Escape backslash and quotes manually
        s_escaped = (
            s.replace("\\", "\\\\")
             .replace('"', '\\"')
             .replace("\b", "\\b")
             .replace("\f", "\\f")
             .replace("\n", "\\n")
             .replace("\r", "\\r")
             .replace("\t", "\\t")
        )
        return f'"{s_escaped}"'

    json_string_st = st.deferred(lambda: st.just(json_string()))

    # JSON number
    # Use Hypothesis built-in floats but convert to JSON number strings
    def json_number():
        # Generate floats and ints, convert to JSON number strings
        # Limit floats to finite values, no NaN or inf
        n = draw(
            st.one_of(
                st.integers(min_value=-10**6, max_value=10**6),
                st.floats(allow_nan=False, allow_infinity=False, width=32),
            )
        )
        # Format number as JSON number string
        if isinstance(n, int):
            return str(n)
        else:
            # Use repr to get decimal notation, but avoid scientific notation if possible
            s = repr(n)
            # JSON allows scientific notation, so repr is fine
            return s

    json_number_st = st.deferred(lambda: st.just(json_number()))

    # Recursive JSON value strategy
    def json_value():
        # Use recursive to build nested arrays and objects
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_null,
            json_true,
            json_false,
        )

        # Recursive containers
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.builds(
                    lambda pairs: "{" + ",".join(pairs) + "}" if pairs else "{}",
                    st.lists(
                        st.tuples(
                            # pair: STRING : value
                            # STRING key
                            st.deferred(lambda: json_string_st),
                            # value
                            children,
                        ),
                        max_size=3,
                    ).map(
                        lambda pairs: [f"{k}:{v}" for k, v in pairs]
                    ),
                ),
                # array: [ value (, value)* ] or []
                st.builds(
                    lambda values: "[" + ",".join(values) + "]" if values else "[]",
                    st.lists(children, max_size=3),
                ),
            ),
            max_leaves=5,
        )

    # Draw a JSON value string
    json_str = draw(json_value())

    # Return as bytes
    return json_str.encode("utf-8")