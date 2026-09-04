from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # JSON strings: roughly matching grammar STRING (no control chars, escapes simplified)
    json_string = st.text(
        alphabet=(
            # safe codepoints excluding control chars and backslash and quote
            ''.join(chr(c) for c in range(0x20, 0x7F) if c not in (0x22, 0x5C))
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('"', '\\"').replace('\\', '\\\\') + '"')

    # Recursive JSON values: objects, arrays, or primitives
    def json_value():
        # Use recursive to bound size and depth
        return st.recursive(
            base=st.one_of(json_string, json_number, json_true, json_false, json_null),
            extend=lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string,
                    values=children,
                    min_size=0,
                    max_size=3,
                    # keys must be unique, dictionary ensures that
                ).map(lambda d: (
                    "{" +
                    ",".join(f"{k}:{v}" for k, v in d.items()) +
                    "}"
                )),
                # array: [ value (, value)* ] or []
                st.lists(children, min_size=0, max_size=4).map(
                    lambda vs: "[" + ",".join(vs) + "]"
                ),
            ),
            max_leaves=10,
        )

    val = draw(json_value())
    return val.encode("utf-8")