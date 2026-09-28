from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base leaf strategies for JSON values
    json_string = st.text(
        alphabet=st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cs', 'Cc'),
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    json_number = st.floats(allow_nan=False, allow_infinity=False).map(lambda f: str(f))
    # Also allow integers as numbers
    json_int = st.integers(min_value=-1_000_000, max_value=1_000_000).map(str)
    json_number = st.one_of(json_int, json_number)

    json_const = st.sampled_from(["true", "false", "null"])

    # Recursive definition for JSON values
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
                # Array: [ value (, value)* ] or []
                st.builds(
                    lambda vals: "[" + ",".join(vals) + "]",
                    st.lists(children, max_size=3),
                ),
            ),
            max_leaves=10,
        )

    val = draw(json_value())
    return val.encode("utf-8")