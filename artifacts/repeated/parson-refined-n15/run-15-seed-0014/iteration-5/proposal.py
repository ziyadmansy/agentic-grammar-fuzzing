from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: use JSON string encoding with escapes
    json_string = st.text(
        st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # NUMBER: use Hypothesis floats and ints, then convert to JSON number string
    def number_to_json(n):
        # Format number as JSON number string, avoiding trailing .0 for ints
        if isinstance(n, int):
            return str(n)
        else:
            # Use repr to get a compact float representation
            return repr(n)

    json_number = st.one_of(
        st.integers(min_value=-(10**9), max_value=10**9),
        st.floats(allow_nan=False, allow_infinity=False, width=32),
    ).map(number_to_json)

    # Recursive JSON value strategy
    # Use st.recursive to build nested arrays and objects, bounded size
    base = st.one_of(json_string, json_number, json_null, json_true, json_false)

    # Forward declare value for recursion
    def json_value():
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or empty {}
                st.dictionaries(
                    keys=json_string,
                    values=children,
                    min_size=0,
                    max_size=5,
                ).map(
                    lambda d: (
                        "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"
                        if d else "{}"
                    )
                ),
                # array: [ value (, value)* ] or empty []
                st.lists(children, min_size=0, max_size=5).map(
                    lambda l: "[" + ",".join(l) + "]" if l else "[]"
                ),
            ),
            max_leaves=10,
        )

    value_str = draw(json_value())
    return value_str.encode("utf-8")