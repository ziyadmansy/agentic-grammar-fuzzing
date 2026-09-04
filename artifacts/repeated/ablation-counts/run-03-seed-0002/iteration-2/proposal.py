from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, "g"))
    # JSON strings: roughly matching grammar STRING (no control chars, escapes simplified)
    json_string = st.text(
        alphabet=(
            # safe code points excluding control chars and backslash and quote
            st.characters(
                blacklist_characters=['\\', '"'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('"', '\\"').replace('\\', '\\\\') + '"')

    # Forward declare value to allow recursion
    # We'll build value recursively with bounded depth
    # Use st.recursive to build obj and arr from primitives

    # Primitive values for recursion base
    json_primitive = st.one_of(json_string, json_number, json_null, json_true, json_false)

    # Recursive containers: obj and arr
    def json_containers(children):
        # pair: STRING ':' value
        pair = st.tuples(json_string, children).map(lambda p: f"{p[0]}:{p[1]}")

        # obj: '{' pair (',' pair)* '}' or '{}'
        obj = st.lists(pair, max_size=5).map(
            lambda pairs: "{" + ",".join(pairs) + "}" if pairs else "{}"
        )

        # arr: '[' value (',' value)* ']' or '[]'
        arr = st.lists(children, max_size=5).map(
            lambda values: "[" + ",".join(values) + "]" if values else "[]"
        )

        return st.one_of(obj, arr)

    json_value = st.recursive(json_primitive, json_containers, max_leaves=10)

    # Compose full json with EOF (just the value here)
    result = draw(json_value)
    return result.encode("utf-8")