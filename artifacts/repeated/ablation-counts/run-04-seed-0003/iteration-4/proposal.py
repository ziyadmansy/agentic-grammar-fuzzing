from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, '.15g'))
    # JSON strings: roughly matching grammar STRING (no control chars, escaped quotes and backslashes)
    json_string = st.text(
        alphabet=(
            # safe codepoints except control chars and backslash and quote
            ''.join(chr(c) for c in range(0x20, 0x7F) if c not in (0x22, 0x5C))
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # Recursive JSON values: string, number, obj, arr, true, false, null
    # Use recursive to keep size bounded
    def json_value():
        # Forward declaration for recursion
        return st.deferred(lambda: json_value_inner())

    # Object pairs: STRING ':' value
    @st.composite
    def json_pair(draw):
        key = draw(json_string)
        val = draw(json_value())
        return f"{key}:{val}"

    @st.composite
    def json_obj(draw):
        # Either empty or non-empty object
        empty = draw(st.booleans())
        if empty:
            return "{}"
        else:
            # up to 3 pairs to keep size bounded
            pairs = draw(st.lists(json_pair(), min_size=1, max_size=3))
            return "{" + ",".join(pairs) + "}"

    @st.composite
    def json_arr(draw):
        empty = draw(st.booleans())
        if empty:
            return "[]"
        else:
            # up to 3 elements to keep size bounded
            elems = draw(st.lists(json_value(), min_size=1, max_size=3))
            return "[" + ",".join(elems) + "]"

    def json_value_inner():
        # Compose all possible JSON values
        base = st.one_of(
            json_string,
            json_number,
            json_null,
            json_true,
            json_false,
        )
        # Use recursive to add obj and arr with bounded depth
        return st.recursive(
            base,
            lambda children: st.one_of(
                json_obj(),
                json_arr(),
            ),
            max_leaves=10,
        )

    # Draw the top-level JSON value and append EOF (implicit)
    val = draw(json_value())
    return val.encode("utf-8")