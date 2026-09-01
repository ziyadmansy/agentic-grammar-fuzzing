from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then JSON-encode them.
    # To keep near-valid cases, sometimes produce invalid escapes or control chars.
    def json_string():
        # safe chars excluding control chars and quotes/backslash
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Occasionally insert escapes or invalid escapes
        def string_chars():
            # 80% safe char, 20% escape or control char
            return st.one_of(
                safe_chars,
                st.sampled_from(['\\', '"']),  # invalid inside string without escape
                st.characters(max_codepoint=0x1F),  # control chars (invalid)
                st.sampled_from(['\\b', '\\f', '\\n', '\\r', '\\t', '\\u1234']),
            )
        # But to keep it simpler and mostly valid, generate normal strings and then JSON-encode
        s = draw(st.text(min_size=0, max_size=20))
        # Encode with json.dumps to get valid JSON string
        import json
        encoded = json.dumps(s)
        return encoded

    # NUMBER: generate numbers as strings matching the grammar
    def json_number():
        # Generate float or int as string
        # Use hypothesis floats but convert to JSON number string
        # Limit range to avoid scientific notation with huge exponents
        f = draw(st.one_of(
            st.integers(min_value=-10**6, max_value=10**6).map(str),
            st.floats(min_value=-1e6, max_value=1e6, allow_infinity=False, allow_nan=False)
            .map(lambda x: format(x, '.6g'))
        ))
        return f

    # Recursive JSON value generator
    # Use st.recursive to bound size and depth
    def json_value():
        base = st.one_of(
            st.just(json_null),
            st.just(json_true),
            st.just(json_false),
            st.builds(lambda s: s, json_string()),
            st.builds(lambda n: n, json_number()),
        )

        def extend(children):
            # obj: '{' pair (',' pair)* '}' or '{}'
            # pair: STRING ':' value
            # arr: '[' value (',' value)* ']' or '[]'
            pair = st.tuples(json_string(), children).map(lambda p: f"{p[0]}:{p[1]}")
            obj = st.one_of(
                st.just("{}"),
                st.lists(pair, min_size=1, max_size=4).map(lambda pairs: "{" + ",".join(pairs) + "}"),
            )
            arr = st.one_of(
                st.just("[]"),
                st.lists(children, min_size=1, max_size=4).map(lambda vals: "[" + ",".join(vals) + "]"),
            )
            return st.one_of(obj, arr)

        return st.recursive(base, extend, max_leaves=10)

    # Compose full JSON text: value + EOF
    val = draw(json_value())
    return val.encode("utf-8")