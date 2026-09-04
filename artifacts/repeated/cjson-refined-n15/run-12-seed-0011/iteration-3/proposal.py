from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string: use Hypothesis text with safe codepoints excluding control chars and quotes/backslash
    json_string = st.text(
        alphabet=st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s + '"')

    # JSON number: use Hypothesis floats and ints converted to JSON number strings
    # To keep it simple, generate strings matching the NUMBER grammar
    json_number = st.one_of(
        st.integers(min_value=-(10**6), max_value=10**6).map(str),
        st.floats(min_value=-1e6, max_value=1e6, allow_infinity=False, allow_nan=False).map(lambda f: format(f, 'g')),
    )

    # Forward declaration for recursive structures
    # We'll build value strategy recursively
    def json_value():
        # Use st.deferred to allow recursion
        return st.deferred(lambda: st.one_of(
            json_string,
            json_number,
            json_object,
            json_array,
            json_true,
            json_false,
            json_null,
        ))

    # JSON pair: STRING ':' value
    @st.composite
    def json_pair(draw):
        key = draw(json_string)
        val = draw(json_value())
        return f"{key}:{val}"

    # JSON object: '{' pair (',' pair)* '}' or '{}'
    json_object = st.recursive(
        st.just("{}"),
        lambda children: st.builds(
            lambda pairs: "{" + ",".join(pairs) + "}",
            st.lists(json_pair(), min_size=1, max_size=4),
        ),
        max_leaves=4,
    )

    # JSON array: '[' value (',' value)* ']' or '[]'
    json_array = st.recursive(
        st.just("[]"),
        lambda children: st.builds(
            lambda values: "[" + ",".join(values) + "]",
            st.lists(json_value(), min_size=1, max_size=4),
        ),
        max_leaves=4,
    )

    # Now draw a full JSON value and encode as bytes
    result = draw(json_value())
    return result.encode("utf-8")