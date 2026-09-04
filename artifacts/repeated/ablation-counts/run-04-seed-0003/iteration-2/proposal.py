from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, '.15g'))
    # STRING: roughly matching grammar, allowing escape sequences and safe codepoints
    # We'll generate Python strings and then encode as JSON strings using repr-like escaping
    # but Hypothesis has a built-in json string strategy:
    json_string = st.text(
        alphabet=(
            # safe codepoints: exclude control chars and quotes/backslash
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # Recursive definition for arrays and objects
    # We'll define values recursively with bounded depth and size
    # Use st.recursive to keep recursion bounded

    base = st.one_of(json_null, json_true, json_false, json_number, json_string)

    def json_obj():
        # pair: STRING ':' value
        pair = st.tuples(json_string, values).map(lambda p: f"{p[0]}:{p[1]}")
        # object: '{' pair (',' pair)* '}' or '{}'
        return st.one_of(
            st.just("{}"),
            st.lists(pair, min_size=1, max_size=5).map(lambda pairs: "{" + ",".join(pairs) + "}")
        )

    def json_arr():
        # array: '[' value (',' value)* ']' or '[]'
        return st.one_of(
            st.just("[]"),
            st.lists(values, min_size=1, max_size=5).map(lambda vs: "[" + ",".join(vs) + "]")
        )

    # Use st.recursive to define values including arrays and objects
    values = st.recursive(
        base,
        lambda children: st.one_of(json_obj(), json_arr()),
        max_leaves=10,
    )

    # Draw a value and encode as bytes
    result = draw(values)
    return result.encode("utf-8")