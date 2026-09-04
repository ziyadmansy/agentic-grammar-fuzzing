from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # JSON string: simplified safe string without control chars or escapes for simplicity
    json_string = st.text(
        alphabet=(
            # safe codepoints except " and \ and control chars
            ''.join(chr(c) for c in range(0x20, 0x7F) if chr(c) not in ['"', '\\'])
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s + '"')

    # Forward declaration for recursive structures
    # We build value recursively: string, number, obj, arr, true, false, null
    def json_value():
        # We'll define obj and arr inside to use recursion
        return st.deferred(lambda: json_value_inner)

    # Object: '{' pair (',' pair)* '}' or '{}'
    # pair: STRING ':' value
    @st.composite
    def json_pair(draw):
        key = draw(json_string)
        val = draw(json_value())
        return f"{key}:{val}"

    @st.composite
    def json_obj(draw):
        # empty or 1-3 pairs
        pairs = draw(st.lists(json_pair(), min_size=0, max_size=3))
        if len(pairs) == 0:
            return "{}"
        else:
            return "{" + ",".join(pairs) + "}"

    # Array: '[' value (',' value)* ']' or '[]'
    @st.composite
    def json_arr(draw):
        vals = draw(st.lists(json_value(), min_size=0, max_size=3))
        if len(vals) == 0:
            return "[]"
        else:
            return "[" + ",".join(vals) + "]"

    # Compose value with recursion bounded by max_leaves
    json_value_inner = st.recursive(
        base=st.one_of(json_string, json_number, json_true, json_false, json_null),
        extend=lambda children: st.one_of(json_obj(), json_arr()),
        max_leaves=10,
    )

    # Draw the top-level JSON value and append EOF (nothing)
    val = draw(json_value_inner)
    return val.encode("utf-8")