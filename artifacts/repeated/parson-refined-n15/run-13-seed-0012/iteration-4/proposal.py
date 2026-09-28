from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # JSON strings with safe codepoints, avoiding control chars and escapes for simplicity
    json_string = st.text(
        alphabet=(
            # safe codepoints excluding control chars and quotes/backslash
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        ),
        max_size=20,
    ).map(lambda s: '"' + s + '"')

    # Recursive JSON value strategy
    def json_value():
        # Use recursive to build nested arrays and objects
        base = st.one_of(json_string, json_number, json_null, json_true, json_false)

        # Compose arrays and objects recursively
        return st.recursive(
            base,
            lambda children: st.one_of(
                # array: [value, value, ...]
                children.flatmap(
                    lambda v: st.lists(children, max_size=3).map(
                        lambda vs: "[" + ",".join([v] + vs) + "]"
                    )
                ),
                # object: {"key": value, ...}
                st.dictionaries(
                    keys=st.text(
                        alphabet=(
                            st.characters(
                                blacklist_characters=['"', '\\'],
                                min_codepoint=0x20,
                                max_codepoint=0x10FFFF,
                            )
                        ),
                        max_size=10,
                    ).map(lambda s: '"' + s + '"'),
                    values=children,
                    max_size=3,
                ).map(
                    lambda d: "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"
                ),
            ),
            max_leaves=10,
        )

    result = draw(json_value())
    return result.encode("utf-8")