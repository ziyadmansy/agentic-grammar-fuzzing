from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Define a recursive strategy for JSON values
    # Base cases: STRING, NUMBER, true, false, null
    base = st.one_of(
        st.text(
            alphabet=st.characters(
                blacklist_categories=('Cs', 'Cc'),  # exclude surrogate and control chars
                blacklist_characters=['\\', '"']
            ),
            min_size=0,
            max_size=10
        ).map(lambda s: '"' + s.replace('"', '\\"') + '"'),
        # Numbers as strings to produce valid JSON number literals
        st.integers(min_value=-1000, max_value=1000).map(str),
        st.floats(allow_infinity=False, allow_nan=False, width=32).map(lambda f: format(f, 'g')),
        st.sampled_from(['true', 'false', 'null'])
    )

    # Recursive strategy for arrays and objects
    def json_value():
        return st.recursive(
            base,
            lambda children: st.one_of(
                # array: [value, value, ...]
                st.lists(children, min_size=0, max_size=3).map(lambda vs: '[' + ','.join(vs) + ']'),
                # object: {"key": value, ...}
                st.dictionaries(
                    keys=st.text(
                        alphabet=st.characters(
                            blacklist_categories=('Cs', 'Cc'),
                            blacklist_characters=['\\', '"']
                        ),
                        min_size=1,
                        max_size=10
                    ).map(lambda s: '"' + s.replace('"', '\\"') + '"'),
                    values=children,
                    min_size=0,
                    max_size=3
                ).map(lambda d: '{' + ','.join(f'{k}:{v}' for k, v in d.items()) + '}')
            ),
            max_leaves=10
        )

    val = draw(json_value())
    return val.encode('utf-8')