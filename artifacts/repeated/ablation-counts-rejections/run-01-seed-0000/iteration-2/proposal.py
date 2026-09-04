from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON strings: use Hypothesis built-in string strategy with safe characters
    # We use a conservative character set to avoid control chars and unescaped quotes
    json_string = st.text(
        alphabet=(
            # safe unicode codepoints excluding control chars and quotes/backslash
            st.characters(
                blacklist_characters=['"', '\\'],
                blacklist_categories=('Cc',)
            )
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # JSON numbers: use Hypothesis floats converted to JSON number strings
    # Limit floats to finite values and reasonable range
    def float_to_json_number(f):
        # Format float to JSON number string without trailing .0 if possible
        if f == int(f):
            return str(int(f))
        else:
            return repr(f)

    json_number = st.floats(
        allow_nan=False,
        allow_infinity=False,
        width=32,
        min_value=-1e6,
        max_value=1e6,
    ).map(float_to_json_number)

    # Recursive JSON value strategy
    # We'll build it with st.recursive, limiting max depth and size
    # Compose obj and arr from smaller values

    # Forward declaration for value strategy
    # We'll define value_base and then value = st.recursive(value_base, ...)

    value_base = st.one_of(
        json_string,
        json_number,
        json_null,
        json_true,
        json_false,
    )

    # obj: '{' pair (',' pair)* '}' or '{}'
    # pair: STRING ':' value
    # We'll limit number of pairs to max 3 to keep size bounded

    @st.composite
    def json_obj(draw):
        # number of pairs 0..3
        n = draw(st.integers(min_value=0, max_value=3))
        if n == 0:
            return "{}"
        pairs = []
        for _ in range(n):
            key = draw(json_string)
            val = draw(value)
            pairs.append(f"{key}:{val}")
        return "{" + ",".join(pairs) + "}"

    # arr: '[' value (',' value)* ']' or '[]'
    # limit length to max 3

    @st.composite
    def json_arr(draw):
        n = draw(st.integers(min_value=0, max_value=3))
        if n == 0:
            return "[]"
        vals = [draw(value) for _ in range(n)]
        return "[" + ",".join(vals) + "]"

    # Now define value as recursive strategy
    # We use st.recursive with base value_base and extend with obj and arr

    # We need to define value after json_obj and json_arr are defined,
    # but json_obj and json_arr depend on value.
    # To break this cycle, we define value as a placeholder and then assign.

    # We'll use a trick: define value as a st.Deferred strategy

    value = st.deferred(lambda: st.one_of(
        value_base,
        json_obj(),
        json_arr(),
    ))

    # Now json_obj and json_arr can use value

    # Redefine json_obj and json_arr with the updated value

    @st.composite
    def json_obj(draw):
        n = draw(st.integers(min_value=0, max_value=3))
        if n == 0:
            return "{}"
        pairs = []
        for _ in range(n):
            key = draw(json_string)
            val = draw(value)
            pairs.append(f"{key}:{val}")
        return "{" + ",".join(pairs) + "}"

    @st.composite
    def json_arr(draw):
        n = draw(st.integers(min_value=0, max_value=3))
        if n == 0:
            return "[]"
        vals = [draw(value) for _ in range(n)]
        return "[" + ",".join(vals) + "]"

    # Now redefine value with these updated composites

    value = st.deferred(lambda: st.one_of(
        value_base,
        json_obj(),
        json_arr(),
    ))

    # Draw a JSON value and append EOF (implicitly by returning full JSON string)
    json_text = draw(value)
    return json_text.encode("utf-8")