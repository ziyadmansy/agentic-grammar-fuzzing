from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, '.15g'))
    json_string = st.text(
        alphabet=(
            # SAFECODEPOINT: any Unicode codepoint except control chars and " \ 
            # We'll exclude control chars (U+0000-U+001F) and " and \ explicitly
            c for c in (chr(i) for i in range(0x20, 0xD800))
            if c not in ('"', '\\')
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # Recursive JSON values: obj and arr
    # Use st.recursive to keep size bounded and avoid infinite recursion
    def json_value():
        base = st.one_of(json_string, json_number, json_null, json_true, json_false)
        return st.recursive(
            base,
            lambda children: st.one_of(
                # obj: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string,
                    values=children,
                    min_size=0,
                    max_size=3,
                ).map(
                    lambda d: (
                        "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"
                        if d else "{}"
                    )
                ),
                # arr: [ value (, value)* ] or []
                st.lists(children, min_size=0, max_size=3).map(
                    lambda l: "[" + ",".join(l) + "]" if l else "[]"
                ),
            ),
            max_leaves=10,
        )

    json_val = draw(json_value())
    return json_val.encode("utf-8")