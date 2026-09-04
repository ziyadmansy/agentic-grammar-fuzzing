from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # JSON string strategy
    # Use safe unicode codepoints excluding control chars and quotes/backslash
    # Escape sequences handled by JSON encoder, so generate safe strings
    json_string = st.text(
        alphabet=st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        ),
        min_size=0,
        max_size=20
    ).map(lambda s: '"' + s.replace('\b', '\\b').replace('\f', '\\f').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t') + '"')

    # JSON number strategy
    json_number = st.one_of(
        st.integers(min_value=-1_000_000, max_value=1_000_000).map(str),
        st.floats(min_value=-1e6, max_value=1e6, allow_infinity=False, allow_nan=False).map(lambda f: format(f, 'g'))
    )

    # JSON constants
    json_const = st.sampled_from(['true', 'false', 'null'])

    # Recursive JSON value strategy
    # Use bounded recursion to avoid too deep structures
    def json_value():
        return st.recursive(
            base=st.one_of(json_string, json_number, json_const),
            extend=lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.builds(
                    lambda pairs: '{' + ','.join(pairs) + '}',
                    st.lists(
                        st.tuples(json_string, children),
                        max_size=3
                    ).map(lambda pairs: [f'{k}:{v}' for k, v in pairs])
                ),
                # array: [ value (, value)* ] or []
                st.builds(
                    lambda values: '[' + ','.join(values) + ']',
                    st.lists(children, max_size=3)
                )
            ),
            max_leaves=10
        )

    val = draw(json_value())
    return val.encode('utf-8')