from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_string = st.text(
        alphabet=st.characters(
            blacklist_characters=['\\', '"'],
            blacklist_categories=('Cc',)  # control chars
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('"', '\\"') + '"')

    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: str(f))

    json_const = st.sampled_from(["true", "false", "null"])

    # Recursive strategy for JSON values
    def json_value():
        return st.recursive(
            base=st.one_of(json_string, json_number, json_const),
            extend=lambda children: st.one_of(
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
                # array: [ value (, value)* ] or []
                st.builds(
                    lambda elements: "[" + ",".join(elements) + "]",
                    st.lists(children, max_size=3),
                ),
            ),
            max_leaves=10,
        )

    result = draw(json_value())
    return result.encode("utf-8")