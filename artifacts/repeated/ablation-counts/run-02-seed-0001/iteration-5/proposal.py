from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic leaf strategies
    json_string = st.text(
        alphabet=st.characters(
            blacklist_characters=['\\', '"', '\u0000', '\u0001', '\u0002', '\u0003', '\u0004', '\u0005', '\u0006',
                                  '\u0007', '\u0008', '\u000B', '\u000C', '\u000E', '\u000F', '\u0010', '\u0011',
                                  '\u0012', '\u0013', '\u0014', '\u0015', '\u0016', '\u0017', '\u0018', '\u0019',
                                  '\u001A', '\u001B', '\u001C', '\u001D', '\u001E', '\u001F'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=10,
    ).map(lambda s: '"' + s.replace('"', '\\"').replace('\\', '\\\\') + '"')

    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: str(f))

    # Forward declaration for recursive strategy
    # We'll define json_value recursively below
    # We use st.recursive to keep recursion bounded

    # Placeholders for recursive definition
    # We will define json_value after obj and arr

    # obj: '{' pair (',' pair)* '}' | '{}'
    # pair: STRING ':' value
    # arr: '[' value (',' value)* ']' | '[]'

    # To avoid infinite recursion, limit max depth and max size of collections

    # Define pair strategy
    # pair is STRING ':' value
    # We'll define pair after json_value is defined

    # Define json_value recursively
    # First define base cases (leaves)
    json_base = st.one_of(
        json_string,
        json_number,
        st.just("true"),
        st.just("false"),
        st.just("null"),
    )

    # We will define json_value recursively with obj and arr

    # Forward declare json_value for pair
    # Use a helper function to build recursive strategy

    def json_value_strategy():
        # pair strategy depends on json_value
        def pair():
            return st.tuples(json_string, json_value).map(lambda p: p[0] + ":" + p[1])

        # obj strategy
        obj_inner = st.lists(pair(), max_size=3).map(
            lambda pairs: "{" + ",".join(pairs) + "}" if pairs else "{}"
        )

        # arr strategy
        arr_inner = st.lists(json_value, max_size=3).map(
            lambda values: "[" + ",".join(values) + "]" if values else "[]"
        )

        # recursive json_value
        return st.recursive(
            json_base,
            lambda children: st.one_of(obj_inner, arr_inner),
            max_leaves=10,
        )

    json_value = json_value_strategy()

    # Draw a full json value and add EOF (implicit by returning bytes)
    result = draw(json_value)
    return result.encode("utf-8")