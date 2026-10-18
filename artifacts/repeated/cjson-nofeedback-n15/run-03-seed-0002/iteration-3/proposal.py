from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: use Hypothesis built-in json string strategy for valid escapes
    json_string = st.text(
        st.characters(
            blacklist_characters=['"', '\\', '\u0000', '\u0001', '\u001F'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # NUMBER strategy: generate numbers matching the grammar
    # Use floats and ints, then convert to string
    def number_to_str(n):
        # Format number to JSON number string
        # Use repr to get a valid JSON number representation
        s = repr(n)
        # repr may produce 'inf', 'nan' - avoid those
        if s in ('inf', '-inf', 'nan'):
            return "0"
        return s

    json_number = st.one_of(
        st.integers(min_value=-(10**6), max_value=10**6).map(str),
        st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-(10**6),
            max_value=10**6,
        ).map(number_to_str),
    )

    # Forward declaration for recursive structures
    # We'll define value recursively below

    # Recursive JSON value strategy
    def json_value():
        # Compose the recursive strategy lazily
        return st.recursive(
            st.one_of(
                json_string,
                json_number,
                json_true,
                json_false,
                json_null,
            ),
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

    json_val = draw(json_value())
    return json_val.encode("utf-8")