from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string strategy: use safe unicode codepoints excluding control chars and quotes/backslash
    # We generate strings and then quote them properly
    def json_string():
        # SAFECODEPOINT: ~["\\\u0000-\u001F]
        # We'll generate unicode characters excluding control chars and quotes/backslash
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Limit string length to keep size bounded
        return st.text(safe_char, min_size=0, max_size=20).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    json_number = st.builds(
        lambda n: str(n),
        st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e10,
            max_value=1e10,
        )
    ).map(lambda s: s if '.' in s or 'e' in s or 'E' in s else str(int(float(s))))

    # Recursive JSON value strategy
    # We use st.recursive to build nested objects and arrays
    base = st.one_of(
        json_null,
        json_true,
        json_false,
        json_string(),
        json_number,
    )

    # Compose object and array strategies
    def json_object():
        # pair: STRING ':' value
        # limit number of pairs to keep size bounded
        pair = st.tuples(json_string(), generated_json_value).map(lambda p: f"{p[0]}:{p[1]}")
        # 0 to 5 pairs
        pairs = st.lists(pair, max_size=5)
        return pairs.map(lambda ps: "{" + (",".join(ps)) + "}")

    def json_array():
        # array of values, 0 to 5 elements
        arr = st.lists(generated_json_value, max_size=5)
        return arr.map(lambda vs: "[" + (",".join(vs)) + "]")

    # Use st.recursive to define generated_json_value
    generated_json_value = st.recursive(
        base,
        lambda children: st.one_of(
            json_object(),
            json_array(),
        ),
        max_leaves=10,
    )

    # Draw a value and encode as bytes
    val = draw(generated_json_value)
    return val.encode("utf-8")