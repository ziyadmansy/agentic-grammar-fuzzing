from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON strings: safe unicode codepoints excluding control chars and quotes/backslash
    # Use characters from U+0020 (space) to U+10FFFF excluding quotes and backslash
    # To keep it simple, use st.text with blacklist characters
    json_string = st.text(
        alphabet=(
            chr(i)
            for i in range(0x20, 0xD7FF)
            if chr(i) not in ['"', '\\']
        ),
        min_size=0,
        max_size=10,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # JSON numbers: use Hypothesis floats converted to JSON number strings
    # Limit floats to finite numbers, no NaN or inf
    def number_to_json(n: float) -> str:
        # Format to JSON number string
        # Use repr to preserve precision, but remove trailing .0 if integer
        if n == int(n):
            return str(int(n))
        else:
            return repr(n)

    json_number = st.floats(
        allow_nan=False,
        allow_infinity=False,
        width=32,
        min_value=-1e10,
        max_value=1e10,
    ).map(number_to_json)

    # Recursive JSON values: string, number, object, array, true, false, null
    # Use st.recursive to build nested objects and arrays with bounded depth and size

    base = st.one_of(json_string, json_number, json_null, json_true, json_false)

    # Forward declarations for obj and arr to use in recursive
    # obj: '{' pair (',' pair)* '}' | '{}'
    # pair: STRING ':' value
    # arr: '[' value (',' value)* ']' | '[]'

    # We'll define value recursively below

    @st.composite
    def json_pair(draw):
        k = draw(json_string)
        v = draw(value)
        return f"{k}:{v}"

    @st.composite
    def json_obj(draw):
        # Either empty or 1-3 pairs
        n = draw(st.integers(min_value=0, max_value=3))
        if n == 0:
            return "{}"
        pairs = draw(st.lists(json_pair(), min_size=n, max_size=n))
        return "{" + ",".join(pairs) + "}"

    @st.composite
    def json_arr(draw):
        # Either empty or 1-4 values
        n = draw(st.integers(min_value=0, max_value=4))
        if n == 0:
            return "[]"
        vals = draw(st.lists(value, min_size=n, max_size=n))
        return "[" + ",".join(vals) + "]"

    # Recursive value definition
    value = st.recursive(
        base,
        lambda children: st.one_of(
            json_obj(),
            json_arr(),
        ),
        max_leaves=10,
    )

    # Draw the top-level JSON value and append EOF (nothing)
    result = draw(value)
    return result.encode("utf-8")