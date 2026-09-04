from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy matching JSON string grammar (simplified)
    # Use Hypothesis's built-in json string strategy for safety and coverage
    json_string = st.text(
        alphabet=(
            # safe codepoints excluding control chars and backslash and quote
            st.characters(
                blacklist_characters=['\\', '"'],
                blacklist_categories=('Cc',)
            )
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # NUMBER strategy matching JSON number grammar (simplified)
    json_number = st.one_of(
        st.integers(min_value=-1_000_000, max_value=1_000_000).map(str),
        st.floats(allow_infinity=False, allow_nan=False, width=32).map(lambda f: format(f, 'g'))
    )

    # Recursive strategy for JSON values
    def json_value():
        return st.recursive(
            st.one_of(json_null, json_true, json_false, json_string, json_number),
            lambda children: st.one_of(
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
                st.lists(children, min_size=0, max_size=3).map(
                    lambda l: (
                        '[' + ','.join(l) + ']'
                        if l else '[]'
                    )
                ),
            ),
            max_leaves=10,
        )

    s = json_value()
    js = draw(s)
    return js.encode('utf-8')