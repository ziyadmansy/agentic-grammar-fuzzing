from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, '.15g'))
    # JSON strings with safe codepoints and escapes
    json_string = st.text(
        alphabet=(
            # safe codepoints excluding control chars and " \ 
            ''.join(chr(c) for c in range(0x20, 0x7F) if c not in (0x22, 0x5C))
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # Recursive JSON values
    def json_value():
        # Compose values with recursion bounded by max_leaves
        return st.recursive(
            base=st.one_of(json_string, json_number, json_null, json_true, json_false),
            extend=lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string,
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
                st.lists(children, min_size=0, max_size=4).map(
                    lambda l: (
                        '[' + ','.join(l) + ']'
                        if l else '[]'
                    )
                ),
            ),
            max_leaves=10,
        )

    json_val = draw(json_value())
    return json_val.encode('utf-8')