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
    # STRING: use a safe subset of Unicode codepoints excluding control chars and quotes/backslash
    # We generate strings without control chars and without quotes or backslash to avoid escaping complexity
    json_string = st.text(
        alphabet=(
            chr(i)
            for i in range(0x20, 0xD7FF)
            if chr(i) not in ('"', '\\')
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s + '"')

    # Recursive JSON values: objects and arrays
    # Use bounded recursion to keep size manageable
    def json_value():
        base = st.one_of(
            json_string,
            json_number,
            json_true,
            json_false,
            json_null,
        )
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.builds(
                    lambda pairs: "{" + ",".join(pairs) + "}",
                    st.lists(
                        st.tuples(
                            json_string,
                            children,
                        ).map(lambda t: f"{t[0]}:{t[1]}"),
                        max_size=3,
                    ),
                ),
                st.just("{}"),
                # array: [ value (, value)* ] or []
                st.builds(
                    lambda values: "[" + ",".join(values) + "]",
                    st.lists(children, max_size=3),
                ),
                st.just("[]"),
            ),
            max_leaves=10,
        )

    result = draw(json_value())
    return result.encode("utf-8")