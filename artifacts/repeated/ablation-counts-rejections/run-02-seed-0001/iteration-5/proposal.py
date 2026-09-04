from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string: use a safe subset of unicode characters excluding control chars and quotes/backslash
    # SAFECODEPOINT ~["\\\u0000-\u001F]
    # We'll generate strings with characters in range 0x20-0x10FFFF excluding backslash and quote
    # To keep it simple, use ascii printable except backslash and quote
    safe_char = st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs', 'Po', 'Ps', 'Pe', 'Sm', 'Sc', 'Sk', 'So'),
        blacklist_characters=['\\', '"'],
        min_codepoint=0x20,
        max_codepoint=0x7E,
    )
    json_string = st.text(safe_char, min_size=0, max_size=20).map(lambda s: '"' + s + '"')

    # JSON number: use Hypothesis floats converted to JSON number strings, bounded and finite
    # We'll generate integers and floats with optional exponent
    def number_to_json(n):
        # Format number as JSON number string
        # Use repr for floats to get exponent if needed
        if isinstance(n, int):
            return str(n)
        else:
            # Use format to avoid trailing .0 for integers in float form
            return format(n, '.15g')

    json_number = st.one_of(
        st.integers(min_value=-10**6, max_value=10**6),
        st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
    ).map(number_to_json)

    # Recursive JSON value strategy
    # We'll define a recursive strategy for value that can be string, number, object, array, true, false, null

    # Forward declaration for value
    # Use st.deferred to allow recursion
    @st.composite
    def json_value(draw):
        # Compose the recursive strategy inside
        # Use st.recursive to build nested objects and arrays
        base = st.one_of(
            json_string,
            json_number,
            json_true,
            json_false,
            json_null,
        )
        # Define recursive containers: object and array
        def obj_strategy():
            # pair: STRING ':' value
            pair = st.tuples(json_string, json_value()).map(lambda p: p[0] + ":" + p[1])
            # object: '{' pair (',' pair)* '}' or '{}'
            return st.lists(pair, max_size=5).map(
                lambda pairs: "{" + ",".join(pairs) + "}" if pairs else "{}"
            )

        def arr_strategy():
            # array: '[' value (',' value)* ']' or '[]'
            return st.lists(json_value(), max_size=5).map(
                lambda values: "[" + ",".join(values) + "]" if values else "[]"
            )

        containers = st.one_of(obj_strategy(), arr_strategy())

        return draw(st.recursive(base, lambda children: containers, max_leaves=10))

    # Compose full JSON with EOF
    json_full = json_value().map(lambda s: s)

    s = draw(json_full)
    return s.encode("utf-8")