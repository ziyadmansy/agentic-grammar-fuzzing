from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base leaf strategies for JSON values
    json_string = st.text(
        alphabet=st.characters(
            blacklist_characters=['\\', '"'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('"', '\\"').replace('\\', '\\\\') + '"')

    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: str(f))

    json_const = st.sampled_from(["true", "false", "null"])

    # Recursive JSON value strategy
    def json_value():
        return st.recursive(
            base=st.one_of(json_string, json_number, json_const),
            extend=lambda children: st.one_of(
                # Object: { pair (, pair)* } or {}
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
                # Array: [ value (, value)* ] or []
                st.builds(
                    lambda values: "[" + ",".join(values) + "]",
                    st.lists(children, max_size=3),
                ),
                st.just("[]"),
            ),
            max_leaves=10,
        )

    s = json_value()
    result = draw(s)
    return result.encode("utf-8")