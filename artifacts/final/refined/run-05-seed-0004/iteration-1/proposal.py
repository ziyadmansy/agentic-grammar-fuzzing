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
    )
    # STRING with simple escapes and safe codepoints
    # We'll generate strings with safe codepoints and some escapes
    # To keep it simple, generate unicode strings and then escape quotes and backslashes.
    def json_string():
        # Generate unicode strings excluding control chars and quotes/backslash
        # Then escape quotes and backslashes
        s = draw(
            st.text(
                st.characters(
                    blacklist_characters=['"', '\\'],
                    min_codepoint=0x20,
                    max_codepoint=0x10FFFF,
                ),
                max_size=20,
            )
        )
        # Escape backslashes and quotes
        s_escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{s_escaped}"'

    # Recursive value strategy
    # Use st.recursive to build arrays and objects from primitives
    primitive = st.one_of(
        json_null,
        json_true,
        json_false,
        json_number,
        st.builds(lambda s: s, st.deferred(json_string)),
    )

    # We'll define value recursively
    def value_strategy():
        # Forward declaration for recursion
        return st.recursive(
            primitive,
            lambda children: st.one_of(
                # array: [ value (, value)* ]
                st.lists(children, max_size=3).map(lambda vs: "[" + ",".join(vs) + "]"),
                # object: { pair (, pair)* } or empty {}
                st.dictionaries(
                    keys=st.deferred(json_string),
                    values=children,
                    max_size=3,
                ).map(
                    lambda d: (
                        "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"
                        if d
                        else "{}"
                    )
                ),
            ),
            max_leaves=10,
        )

    val = draw(value_strategy())
    return val.encode("utf-8")