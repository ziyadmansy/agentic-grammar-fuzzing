from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.from_regex(
        r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?",
        fullmatch=True,
        max_size=20,
    )
    # STRING: simplified safe string with escapes, no control chars
    # We'll generate Python strings and then JSON-encode them with escapes
    # but since we must return bytes, we will build strings and encode at the end.
    # To keep it simple, generate strings without control chars or quotes, then add quotes and escapes.
    json_string_content = st.text(
        alphabet=st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=20,
    )

    def json_string(s: str) -> str:
        # Escape backslash and quote
        s = s.replace('\\', '\\\\').replace('"', '\\"')
        # Also escape control chars if any (shouldn't be present)
        # but just in case, replace control chars with \uXXXX
        def esc_char(c):
            if ord(c) < 0x20:
                return f"\\u{ord(c):04x}"
            return c
        s = "".join(esc_char(c) for c in s)
        return f'"{s}"'

    # Recursive JSON value strategy
    # Use st.recursive to build nested arrays and objects
    base = st.one_of(
        json_null,
        json_true,
        json_false,
        json_number,
        json_string_content.map(json_string),
    )

    # To keep sizes bounded, limit max depth and max elements
    max_depth = 4
    max_elements = 4

    def json_obj():
        # pair: STRING ':' value
        pair = st.tuples(json_string_content.map(json_string), json_value).map(
            lambda p: f"{p[0]}:{p[1]}"
        )
        return st.builds(
            lambda pairs: "{" + ",".join(pairs) + "}" if pairs else "{}",
            st.lists(pair, max_size=max_elements),
        )

    def json_arr():
        return st.builds(
            lambda values: "[" + ",".join(values) + "]",
            st.lists(json_value, max_size=max_elements),
        )

    # We need to define json_value recursively, so we use a placeholder first
    # Then redefine json_value with recursive
    # We'll define a function to build recursive strategy

    # Placeholder for json_value to be replaced
    global json_value
    json_value = st.deferred(lambda: base)

    # Now redefine json_value with recursion
    json_value = st.recursive(
        base,
        lambda children: st.one_of(json_obj(), json_arr()),
        max_leaves=100,
    )

    # Draw a JSON string from json_value and encode as utf-8 bytes
    s = draw(json_value)
    return s.encode("utf-8")