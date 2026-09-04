from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, '.15g'))
    # JSON strings: roughly matching grammar STRING (no control chars, escapes)
    # Use ascii letters, digits, and common safe punctuation, plus escapes
    json_string_chars = st.characters(
        blacklist_characters=['"', '\\'],
        blacklist_categories=('Cc',)  # control chars
    )
    # To include escapes, we add them manually
    escape_sequences = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
    # Compose string content from safe chars or escapes
    json_string_content = st.lists(
        st.one_of(
            json_string_chars,
            escape_sequences
        ),
        min_size=0,
        max_size=20
    ).map("".join)
    json_string = json_string_content.map(lambda s: f'"{s}"')

    # Recursive JSON values: string, number, object, array, true, false, null
    # Use st.recursive to keep bounded size and depth
    def json_value():
        base = st.one_of(
            json_string,
            json_number,
            json_true,
            json_false,
            json_null,
        )
        # Forward declare obj and arr to be used inside recursive
        # We'll define them inside the recursive call below

        def obj_strategy():
            # pair: STRING ':' value
            pair = st.tuples(json_string, json_value()).map(lambda p: f"{p[0]}:{p[1]}")
            # object: '{' pair (',' pair)* '}' or '{}'
            # limit number of pairs to keep size bounded
            pairs = st.lists(pair, max_size=5)
            return pairs.map(lambda ps: "{" + ",".join(ps) + "}" if ps else "{}")

        def arr_strategy():
            # array: '[' value (',' value)* ']' or '[]'
            values = st.lists(json_value(), max_size=5)
            return values.map(lambda vs: "[" + ",".join(vs) + "]" if vs else "[]")

        return st.recursive(
            base,
            lambda children: st.one_of(
                obj_strategy(),
                arr_strategy(),
            ),
            max_leaves=10,
        )

    # Compose full JSON with EOF (no trailing data)
    json_full = json_value().map(lambda s: s)

    # Draw one example and encode as bytes
    s = draw(json_full)
    return s.encode("utf-8")