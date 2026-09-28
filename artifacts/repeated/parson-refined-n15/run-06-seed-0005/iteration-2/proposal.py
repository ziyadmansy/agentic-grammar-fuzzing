from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Define base values: strings, numbers, booleans, null
    base = st.one_of(
        # STRING: generate JSON strings with safe codepoints and escapes
        st.text(
            alphabet=(
                # safe codepoints excluding control chars and backslash, quote
                st.characters(
                    blacklist_characters=['\\', '"'],
                    min_codepoint=0x20,
                    max_codepoint=0x10FFFF,
                )
            ),
            min_size=0,
            max_size=10,
        ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'),
        # NUMBER: generate JSON numbers as strings
        st.floats(allow_nan=False, allow_infinity=False, width=32).map(lambda f: str(f)),
        # true, false, null literals
        st.sampled_from(['true', 'false', 'null']),
    )

    # Recursive strategy for JSON values
    def json_value():
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=st.text(
                        alphabet=(
                            st.characters(
                                blacklist_characters=['\\', '"'],
                                min_codepoint=0x20,
                                max_codepoint=0x10FFFF,
                            )
                        ),
                        min_size=1,
                        max_size=10,
                    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'),
                    values=children,
                    min_size=0,
                    max_size=3,
                ).map(
                    lambda d: (
                        '{' + ','.join(f'{k}:{v}' for k, v in d.items()) + '}'
                        if d else '{}'
                    )
                ),
                # array: [ value (, value)* ] or []
                st.lists(children, min_size=0, max_size=3).map(
                    lambda lst: '[' + ','.join(lst) + ']' if lst else '[]'
                ),
            ),
            max_leaves=10,
        )

    result = draw(json_value())
    return result.encode('utf-8')