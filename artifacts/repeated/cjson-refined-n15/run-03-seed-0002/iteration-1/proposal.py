from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # STRING: simplified safe string, escaping minimal chars
    def json_string():
        # safe codepoints excluding control chars and " and \
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # generate short strings to keep size bounded
        return st.text(safe_chars, max_size=10).map(lambda s: '"' + s + '"')

    json_string_st = json_string()

    # Recursive JSON value
    # We use a recursive strategy to build nested objects and arrays
    # Limit max_leaves to keep size bounded
    def json_value():
        base = st.one_of(
            json_string_st,
            json_number,
            json_null,
            json_true,
            json_false,
        )
        # recursive containers: obj and arr
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string_st,
                    values=children,
                    max_size=3,
                ).map(
                    lambda d: (
                        "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"
                        if d else "{}"
                    )
                ),
                # array: [ value (, value)* ] or []
                st.lists(children, max_size=3).map(
                    lambda l: "[" + ",".join(l) + "]" if l else "[]"
                ),
            ),
            max_leaves=10,
        )

    result = draw(json_value())
    return result.encode("utf-8")