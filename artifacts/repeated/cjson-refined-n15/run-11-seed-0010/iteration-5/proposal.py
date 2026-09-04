from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base leaf strategies for JSON values
    json_string = st.text(
        alphabet=st.characters(
            blacklist_characters=['\\', '"', '\u0000', '\u0001', '\u001F'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    json_number = st.floats(allow_nan=False, allow_infinity=False).map(lambda f: format(f, 'g'))

    json_true = st.just("true")
    json_false = st.just("false")
    json_null = st.just("null")

    # Recursive strategy for JSON values
    def json_value():
        return st.recursive(
            base=st.one_of(
                json_string,
                json_number,
                json_true,
                json_false,
                json_null,
            ),
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

    s = json_value()
    result = draw(s)
    return result.encode("utf-8")