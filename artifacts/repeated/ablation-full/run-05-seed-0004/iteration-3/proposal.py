from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode as JSON strings
    # Use hypothesis built-in json string strategy for correctness
    json_string = st.text(
        st.characters(
            blacklist_characters=['"', '\\', '\u0000', '\u0001', '\u0002', '\u0003', '\u0004', '\u0005', '\u0006', '\u0007',
                                  '\u0008', '\u000b', '\u000c', '\u000e', '\u000f', '\u0010', '\u0011', '\u0012', '\u0013',
                                  '\u0014', '\u0015', '\u0016', '\u0017', '\u0018', '\u0019', '\u001a', '\u001b', '\u001c',
                                  '\u001d', '\u001e', '\u001f'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=20,
    )
    # Encode string as JSON string literal with escapes
    def to_json_string(s: str) -> str:
        # Use json.dumps to produce valid JSON string literal
        import json
        return json.dumps(s)

    json_string_literal = json_string.map(to_json_string)

    # NUMBER strategy: generate valid JSON numbers as strings
    # Use hypothesis floats and ints, then convert to JSON number strings
    json_number = st.one_of(
        st.integers(min_value=-(10**10), max_value=10**10).map(str),
        st.floats(allow_nan=False, allow_infinity=False, width=32).map(lambda f: format(f, '.8g')),
    )

    # Recursive JSON value strategy
    # We'll define a recursive strategy that can produce:
    # - primitives: string, number, true, false, null
    # - arrays: [value, ...]
    # - objects: {"string": value, ...}

    # Forward declaration for recursion
    # Use bounded recursion depth and max size to avoid max recursion depth exceeded
    def json_value():
        base = st.one_of(
            json_string_literal,
            json_number,
            json_true,
            json_false,
            json_null,
        )
        # Recursive containers
        return st.recursive(
            base,
            lambda children: st.one_of(
                # array: [value, ...]
                st.lists(children, min_size=0, max_size=5).map(lambda vs: "[" + ",".join(vs) + "]"),
                # object: {"string": value, ...}
                st.dictionaries(
                    json_string.map(lambda s: s[1:-1]),  # strip quotes for keys
                    children,
                    min_size=0,
                    max_size=5,
                ).map(
                    lambda d: "{" + ",".join(f"{to_json_string(k)}:{v}" for k, v in d.items()) + "}"
                ),
            ),
            max_leaves=20,
        )

    val = draw(json_value())
    return val.encode("utf-8")