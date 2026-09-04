from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string with safe codepoints and escapes
    # We limit length to keep sizes bounded
    json_string = st.text(
        alphabet=(
            # safe codepoints excluding control chars and quotes/backslash
            ''.join(chr(c) for c in range(0x20, 0x7F) if c not in (0x22, 0x5C))
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # JSON number: use Hypothesis floats and ints, then convert to JSON number string
    def number_to_json(n):
        # Format floats and ints to JSON number strings
        if isinstance(n, int):
            return str(n)
        else:
            # Use repr to get a valid JSON number representation
            # but avoid inf/nan by filtering in strategy
            return repr(n)

    json_number = st.one_of(
        st.integers(min_value=-(10**9), max_value=10**9),
        st.floats(
            allow_infinity=False,
            allow_nan=False,
            width=32,
            min_value=-1e9,
            max_value=1e9,
        ),
    ).map(number_to_json)

    # Recursive JSON value strategy
    # We use a recursive strategy to build nested objects and arrays,
    # bounded by max_leaves and max_depth to keep sizes reasonable.
    # We include primitives and near-valid cases by allowing empty objects/arrays.

    # Forward declaration for recursive use
    json_value = st.deferred(lambda: json_value_inner)

    # JSON pair: "string" : value
    json_pair = st.tuples(json_string, json_value).map(lambda p: f"{p[0]}:{p[1]}")

    # JSON object: {} or { pair (, pair)* }
    json_object = st.one_of(
        st.just("{}"),
        st.lists(json_pair, min_size=1, max_size=5).map(lambda pairs: "{" + ",".join(pairs) + "}"),
    )

    # JSON array: [] or [ value (, value)* ]
    json_array = st.one_of(
        st.just("[]"),
        st.lists(json_value, min_size=1, max_size=5).map(lambda values: "[" + ",".join(values) + "]"),
    )

    # Compose the recursive value strategy
    json_value_inner = st.recursive(
        st.one_of(json_string, json_number, json_null, json_true, json_false),
        lambda children: st.one_of(json_object, json_array),
        max_leaves=15,
    )

    # Compose the top-level JSON: value + EOF (implicit)
    result = draw(json_value)

    return result.encode("utf-8")