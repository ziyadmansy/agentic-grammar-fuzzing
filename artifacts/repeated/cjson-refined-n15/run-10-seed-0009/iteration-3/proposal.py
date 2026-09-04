from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string with safe codepoints and escapes
    # We'll generate strings that are valid JSON strings (with quotes)
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Include some escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Compose string content from safe chars and escapes
        content = st.lists(st.one_of(safe_char.map(lambda c: c), escapes), max_size=20).map("".join)
        return content.map(lambda s: f'"{s}"')

    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, '.15g'))

    # Recursive JSON value strategy
    # We'll use a bounded recursive strategy to keep sizes manageable
    def json_value():
        base = st.one_of(
            json_string(),
            json_number,
            json_null,
            json_true,
            json_false,
        )

        # Recursive containers: objects and arrays
        # Limit max size to keep example size bounded
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string(),
                    values=children,
                    max_size=5,
                    # JSON objects require keys to be strings, values are JSON values
                ).map(lambda d: "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"),
                # array: [ value (, value)* ] or []
                st.lists(children, max_size=5).map(lambda l: "[" + ",".join(l) + "]"),
            ),
            max_leaves=10,
        )

    val = draw(json_value())
    return val.encode("utf-8")