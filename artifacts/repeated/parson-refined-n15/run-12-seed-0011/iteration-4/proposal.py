from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # String strategy: use Hypothesis built-in text with safe codepoints
    # Limit length to keep size bounded
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

    # Number strategy: use floats and ints, formatted as JSON numbers
    # Limit magnitude and decimal places to keep size bounded
    json_number = st.one_of(
        st.integers(min_value=-1_000_000, max_value=1_000_000).map(str),
        st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ).map(lambda f: format(f, '.6g')),
    )

    # Recursive strategy for JSON values
    # Use st.recursive with a max depth to avoid max recursion depth exceeded
    base = st.one_of(json_null, json_true, json_false, json_string, json_number)

    # Compose objects and arrays recursively
    def json_object():
        # pair: STRING ':' value
        pair = st.tuples(json_string, generated_value).map(lambda p: f"{p[0]}:{p[1]}")
        # limit number of pairs to keep size bounded
        return st.lists(pair, max_size=5).map(
            lambda pairs: "{" + (",".join(pairs) if pairs else "") + "}"
        )

    def json_array():
        # list of values, max size bounded
        return st.lists(generated_value, max_size=5).map(
            lambda values: "[" + (",".join(values) if values else "") + "]"
        )

    # We need to define generated_value as a recursive strategy that includes base and recursive containers
    # Use st.recursive to define generated_value
    generated_value = st.deferred()

    containers = st.one_of(json_object(), json_array())

    generated_value = st.recursive(base, lambda children: containers, max_leaves=20)

    # Draw a value and encode as bytes
    val = draw(generated_value)
    return val.encode("utf-8")