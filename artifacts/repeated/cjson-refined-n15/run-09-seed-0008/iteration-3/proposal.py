from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce JSON strings with safe codepoints and escapes
    # Use a small max_size to keep examples bounded
    json_string = st.text(
        alphabet=(
            # safe codepoints excluding control chars and quotes/backslash
            ''.join(chr(c) for c in range(0x20, 0x7F) if c not in (0x22, 0x5C))
        ),
        min_size=0,
        max_size=10,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # NUMBER strategy: generate JSON numbers as strings
    # Use floats and ints, but stringify them
    json_number = st.one_of(
        st.integers(min_value=-1000, max_value=1000).map(str),
        st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False).map(lambda f: format(f, 'g')),
    )

    # Forward declaration for recursive strategy
    # We'll define json_value recursively below
    # Use st.recursive to keep recursion bounded

    # Base values for recursion
    base = st.one_of(json_string, json_number, json_null, json_true, json_false)

    # Recursive containers: objects and arrays
    # Objects: '{' pair (',' pair)* '}' or '{}'
    # Pairs: STRING ':' value
    # Arrays: '[' value (',' value)* ']' or '[]'

    def json_obj():
        # pairs: STRING ':' value
        pair = st.tuples(json_string, json_value).map(lambda p: p[0] + ':' + p[1])
        # non-empty object: '{' pair (',' pair)* '}'
        non_empty_obj = st.lists(pair, min_size=1, max_size=3).map(lambda pairs: '{' + ','.join(pairs) + '}')
        # empty object: '{}'
        empty_obj = st.just('{}')
        return st.one_of(non_empty_obj, empty_obj)

    def json_arr():
        # array of values
        arr_values = st.lists(json_value, min_size=1, max_size=3).map(lambda vals: '[' + ','.join(vals) + ']')
        empty_arr = st.just('[]')
        return st.one_of(arr_values, empty_arr)

    # Define json_value recursively using st.recursive
    json_value = st.recursive(
        base,
        lambda children: st.one_of(json_obj(), json_arr()),
        max_leaves=5,
    )

    # Draw the final JSON string and encode as bytes
    result = draw(json_value)
    return result.encode('utf-8')