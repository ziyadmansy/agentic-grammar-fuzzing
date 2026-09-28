from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_string = st.text(
        alphabet=st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)

    json_const = st.sampled_from(["true", "false", "null"])

    # Recursive strategy for JSON values
    def json_value():
        return st.recursive(
            base=st.one_of(json_string, json_number, json_const),
            extend=lambda children: st.one_of(
                # Object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string,
                    values=children,
                    min_size=0,
                    max_size=3,
                ).map(
                    lambda d: (
                        "{" + 
                        ",".join(f"{k}:{v}" for k, v in d.items()) + 
                        "}"
                    )
                ),
                # Array: [ value (, value)* ] or []
                st.lists(children, min_size=0, max_size=3).map(
                    lambda l: "[" + ",".join(l) + "]"
                ),
            ),
            max_leaves=10,
        )

    result = draw(json_value())
    return result.encode("utf-8")