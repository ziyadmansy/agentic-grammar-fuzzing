from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # JSON strings: use printable ASCII except control chars and backslash/quote
    json_string = st.text(
        alphabet=(
            # safe code points: no control chars, no backslash, no quote
            st.characters(
                blacklist_characters=['\\', '"'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\b', '\\b').replace('\f', '\\f').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t').replace('"', '\\"').replace('\\', '\\\\') + '"')

    # Forward declare value strategy to allow recursion
    # We'll define it below with st.recursive

    # Compose value base: primitives only
    json_value_base = st.one_of(
        json_string,
        json_number,
        json_null,
        json_true,
        json_false,
    )

    # Recursive containers: object and array
    # Object: { pair (, pair)* } or {}
    # pair: STRING : value
    # Array: [ value (, value)* ] or []

    # Define pair strategy
    def json_pair():
        return st.tuples(json_string, json_value).map(lambda p: p[0] + ":" + p[1])

    # We'll define json_value recursively
    json_value = st.recursive(
        json_value_base,
        lambda children: st.one_of(
            # object
            st.lists(json_pair(), max_size=3).map(
                lambda pairs: "{" + (",".join(pairs) if pairs else "") + "}"
            ),
            # array
            st.lists(children, max_size=3).map(
                lambda values: "[" + (",".join(values) if values else "") + "]"
            ),
        ),
        max_leaves=10,
    )

    # Compose full json: value + EOF (implicit)
    result = draw(json_value)
    return result.encode("utf-8")