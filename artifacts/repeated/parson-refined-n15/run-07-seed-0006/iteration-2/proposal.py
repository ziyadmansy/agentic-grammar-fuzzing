from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_string = st.text(
        alphabet=st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        ),
        min_size=0,
        max_size=20
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)

    json_bool = st.sampled_from(["true", "false"])

    json_null = st.just("null")

    # Recursive JSON value strategy
    def json_value():
        return st.recursive(
            base=st.one_of(json_string, json_number, json_bool, json_null),
            extend=lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
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
                # array: [ value (, value)* ] or []
                st.lists(children, min_size=0, max_size=3).map(
                    lambda l: "[" + ",".join(l) + "]"
                ),
            ),
            max_leaves=10,
        )

    val = draw(json_value())
    return val.encode("utf-8")