from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: use Hypothesis built-in json string strategy for safety
    json_string = st.text(
        alphabet=(
            # safe codepoints excluding control chars and quotes/backslash
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # NUMBER strategy: generate numbers as strings matching the grammar
    def number_to_str(n):
        # Format float or int to JSON number string
        # Use repr to get a JSON-compatible representation
        # But repr may produce trailing .0 for ints, so handle carefully
        if isinstance(n, int):
            return str(n)
        else:
            # Use format with 'g' to avoid trailing zeros
            return format(n, '.15g')

    json_number = st.one_of(
        st.integers(min_value=-10**6, max_value=10**6).map(str),
        st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ).map(number_to_str),
    )

    # Forward declaration for recursive structures
    # We'll define value recursively
    # Use st.recursive to keep size bounded

    # Define value base cases
    json_value_base = st.one_of(
        json_string,
        json_number,
        json_null,
        json_true,
        json_false,
    )

    # Recursive containers: obj and arr
    # pair: STRING ':' value
    @st.composite
    def json_pair(draw):
        k = draw(json_string)
        v = draw(json_value)
        return f"{k}:{v}"

    @st.composite
    def json_obj(draw):
        # Either empty or with pairs
        pairs = draw(
            st.lists(json_pair(), min_size=0, max_size=4)
        )
        if not pairs:
            return "{}"
        else:
            return "{" + ",".join(pairs) + "}"

    @st.composite
    def json_arr(draw):
        # Either empty or with values
        values = draw(
            st.lists(json_value, min_size=0, max_size=4)
        )
        if not values:
            return "[]"
        else:
            return "[" + ",".join(values) + "]"

    # Define value recursively
    json_value = st.recursive(
        json_value_base,
        lambda children: st.one_of(
            json_obj(),
            json_arr(),
        ),
        max_leaves=10,
    )

    # Compose full json: value + EOF (implicit)
    s = draw(json_value)
    return s.encode("utf-8")