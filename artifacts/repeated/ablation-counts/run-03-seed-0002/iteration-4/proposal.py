from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
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

    # To produce valid escaped strings, we allow simple escapes and unicode escapes
    # but for simplicity, we just escape " and \ here.
    # Numbers: integers and floats with optional exponent
    json_number = st.one_of(
        st.integers(min_value=-10**6, max_value=10**6).map(str),
        st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False).map(lambda f: format(f, 'g')),
    )

    # Forward declaration for recursion
    # We'll define value recursively below
    # Use st.recursive to keep recursion bounded

    # Base values: string, number, true, false, null
    base = st.one_of(
        json_string,
        json_number,
        st.just("true"),
        st.just("false"),
        st.just("null"),
    )

    def json_object():
        # pair: STRING ':' value
        pair = st.tuples(json_string, value).map(lambda p: p[0] + ':' + p[1])
        # object: '{' pair (',' pair)* '}' or '{}'
        # limit pairs to max 3 to keep size bounded
        return st.lists(pair, max_size=3).map(
            lambda pairs: '{' + (','.join(pairs) if pairs else '') + '}'
        )

    def json_array():
        # array: '[' value (',' value)* ']' or '[]'
        # limit elements to max 3 to keep size bounded
        return st.lists(value, max_size=3).map(
            lambda values: '[' + (','.join(values) if values else '') + ']'
        )

    # Recursive definition of value
    value = st.recursive(
        base,
        lambda children: st.one_of(
            json_object(),
            json_array(),
        ),
        max_leaves=10,
    )

    # Draw a value and encode as bytes
    s = draw(value)
    return s.encode('utf-8')