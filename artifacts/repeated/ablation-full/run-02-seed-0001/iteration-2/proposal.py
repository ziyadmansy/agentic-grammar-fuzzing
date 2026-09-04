from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: use Hypothesis built-in json string strategy
    json_string = st.text(
        alphabet=(
            # safe codepoints excluding control chars and backslash and quote
            # roughly matching SAFECODEPOINT in grammar
            ''.join(chr(c) for c in range(0x20, 0x7F) if c not in (0x22, 0x5C))
        ),
        min_size=0,
        max_size=10,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # NUMBER strategy: generate numbers as strings matching JSON number grammar
    json_number = st.one_of(
        st.integers(min_value=-1000000, max_value=1000000).map(str),
        st.floats(allow_infinity=False, allow_nan=False, width=32).map(lambda f: format(f, 'g')),
    )

    # Forward declaration for recursive value
    # Use st.recursive to build nested arrays and objects
    def json_value():
        base = st.one_of(
            json_string,
            json_number,
            json_null,
            json_true,
            json_false,
        )
        # recursive containers
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string,
                    values=children,
                    min_size=0,
                    max_size=3,
                ).map(lambda d: (
                    '{' + 
                    ','.join(f'{k}:{v}' for k, v in d.items()) + 
                    '}'
                )),
                # array: [ value (, value)* ] or []
                st.lists(children, min_size=0, max_size=3).map(
                    lambda l: '[' + ','.join(l) + ']'
                ),
            ),
            max_leaves=5,
        )

    s = json_value()
    result = draw(s)
    return result.encode('utf-8')