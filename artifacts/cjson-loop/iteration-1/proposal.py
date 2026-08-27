from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # JSON strings: use ASCII printable except control chars and backslash/quote
    json_string = st.text(
        st.characters(
            blacklist_characters=['\\', '"'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        max_size=20,
    ).map(lambda s: '"' + s.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t') + '"')

    # Recursive JSON values: string, number, obj, arr, true, false, null
    # Use recursive to keep sizes bounded
    def json_value():
        base = st.one_of(json_string, json_number, json_true, json_false, json_null)
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string,
                    values=children,
                    min_size=0,
                    max_size=3,
                ).map(
                    lambda d: (
                        "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"
                        if d else "{}"
                    )
                ),
                # array: [ value (, value)* ] or []
                st.lists(children, min_size=0, max_size=3).map(
                    lambda l: "[" + ",".join(l) + "]" if l else "[]"
                ),
            ),
            max_leaves=10,
        )

    result = draw(json_value())
    return result.encode("utf-8")