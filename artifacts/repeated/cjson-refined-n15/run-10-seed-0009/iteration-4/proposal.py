from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    # STRING: use JSON string escaping, limited length
    json_string = st.text(
        alphabet=(
            # safe codepoints excluding control chars and quotes/backslash
            ''.join(chr(c) for c in range(0x20, 0x7F) if c not in (0x22, 0x5C))
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')
    # NUMBER: generate numbers as strings matching grammar
    # Use floats and ints, then convert to string
    def number_to_str(n):
        # Format to JSON number style
        if n == int(n):
            return str(int(n))
        else:
            # Use repr to keep exponent if any
            return repr(n).replace('inf', '1e+308').replace('nan', '0')
    json_number = st.one_of(
        st.integers(min_value=-10**6, max_value=10**6).map(str),
        st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False).map(number_to_str),
    )
    # Recursive JSON value strategy
    # Use bounded recursion to keep size reasonable
    json_value = st.deferred(lambda: json_value_inner)

    # Pair: STRING ':' value
    json_pair = st.tuples(json_string, json_value).map(lambda p: p[0] + ":" + p[1])

    # Object: '{' pair (',' pair)* '}' or '{}'
    json_obj = st.recursive(
        st.just("{}"),
        lambda children: st.builds(
            lambda pairs: "{" + ",".join(pairs) + "}",
            st.lists(json_pair, min_size=1, max_size=4),
        ),
        max_leaves=10,
    )

    # Array: '[' value (',' value)* ']' or '[]'
    json_arr = st.recursive(
        st.just("[]"),
        lambda children: st.builds(
            lambda values: "[" + ",".join(values) + "]",
            st.lists(json_value, min_size=1, max_size=4),
        ),
        max_leaves=10,
    )

    # Compose json_value_inner from all possibilities
    json_value_inner = st.one_of(
        json_string,
        json_number,
        json_obj,
        json_arr,
        json_true,
        json_false,
        json_null,
    )

    # Draw a full JSON text and encode as bytes
    result = draw(json_value)
    return result.encode("utf-8")