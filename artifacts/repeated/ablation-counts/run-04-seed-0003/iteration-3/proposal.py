from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # STRING: produce valid JSON strings with proper escaping
    # We'll use text with safe codepoints and escape quotes and backslashes
    def json_string():
        # Use characters excluding control chars and backslash and quote
        safe_chars = st.text(
            st.characters(
                blacklist_characters=['\\', '"'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            ),
            min_size=0,
            max_size=20,
        )
        # Escape backslash and quote manually
        def escape_json_string(s: str) -> str:
            s = s.replace('\\', '\\\\').replace('"', '\\"')
            # Also escape control chars if any slipped through (unlikely)
            return s
        return safe_chars.map(escape_json_string).map(lambda s: f'"{s}"')

    json_string = json_string()

    # Recursive JSON value strategy
    # We'll define a function to build recursive JSON values
    def json_value():
        # Use recursive to build nested arrays and objects
        base = st.one_of(json_string, json_number, json_true, json_false, json_null)
        # Recursive containers
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string,
                    values=children,
                    min_size=0,
                    max_size=3,
                ).map(
                    lambda d: (
                        "{" + 
                        ",".join(f"{k}:{v}" for k, v in d.items()) + 
                        "}"
                    )
                ),
                # array: [ value (, value)* ] or []
                st.lists(children, min_size=0, max_size=3).map(
                    lambda l: "[" + ",".join(l) + "]"
                ),
            ),
            max_leaves=10,
        )

    val = draw(json_value())
    return val.encode("utf-8")