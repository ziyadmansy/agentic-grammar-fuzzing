from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_bool = st.sampled_from(["true", "false"])
    json_number = st.floats(allow_nan=False, allow_infinity=False).map(str)
    # JSON strings: use Hypothesis' built-in text with safe characters
    json_string = st.text(
        alphabet=(
            # safe Unicode code points excluding control chars and quotes/backslash
            c for c in map(chr, range(0x20, 0x7F))
            if c not in ['"', '\\']
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # Forward declaration for recursive JSON values
    # Use bounded recursion depth and size to keep examples manageable
    def json_value():
        return st.recursive(
            base=st.one_of(json_null, json_bool, json_number, json_string),
            extend=lambda children: st.one_of(
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

    s = json_value()
    js = draw(s)
    return js.encode("utf-8")