from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_string = st.text(
        alphabet=st.characters(
            blacklist_characters=['\\', '"'],
            blacklist_categories=('Cc',),
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('"', '\\"').replace('\\', '\\\\') + '"')

    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: str(f))
    # Also allow integers as numbers
    json_int = st.integers(min_value=-10**6, max_value=10**6).map(str)
    json_number = st.one_of(json_int, json_number)

    json_true = st.just("true")
    json_false = st.just("false")
    json_null = st.just("null")

    # Forward declaration for recursion
    # We'll build value strategy recursively
    def json_value():
        return st.deferred(lambda: value_strategy)

    # Pair: STRING ':' value
    @st.composite
    def pair(draw):
        key = draw(json_string)
        val = draw(json_value())
        return f"{key}:{val}"

    # Object: '{' pair (',' pair)* '}' or '{}'
    @st.composite
    def obj(draw):
        # Limit number of pairs to keep size bounded
        pairs = draw(st.lists(pair(), max_size=5))
        if pairs:
            return "{" + ",".join(pairs) + "}"
        else:
            return "{}"

    # Array: '[' value (',' value)* ']' or '[]'
    @st.composite
    def arr(draw):
        elements = draw(st.lists(json_value(), max_size=5))
        if elements:
            return "[" + ",".join(elements) + "]"
        else:
            return "[]"

    # Compose value strategy recursively
    value_strategy = st.recursive(
        st.one_of(
            json_string,
            json_number,
            json_true,
            json_false,
            json_null,
        ),
        lambda children: st.one_of(
            obj(),
            arr(),
        ),
        max_leaves=10,
    )

    result = draw(value_strategy)
    return result.encode("utf-8")