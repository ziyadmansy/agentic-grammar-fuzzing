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
    )
    # STRING: roughly matching grammar, allowing escapes and safe codepoints
    # We'll use Hypothesis built-in json string strategy for simplicity and correctness
    json_string = st.text(
        alphabet=(
            # safe codepoints excluding control chars and quotes/backslash
            "".join(
                chr(c)
                for c in range(0x20, 0xD7FF)
                if c not in (0x22, 0x5C)
            )
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # Recursive JSON value strategy
    # Use bounded recursion to limit size and depth
    def json_value():
        # base cases
        base = st.one_of(
            json_string,
            json_number,
            json_null,
            json_true,
            json_false,
        )
        # recursive cases: obj and arr
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.builds(
                    lambda pairs: "{" + ",".join(pairs) + "}",
                    st.lists(
                        st.tuples(
                            json_string,
                            children,
                        ).map(lambda t: f"{t[0]}:{t[1]}"),
                        max_size=4,
                    ),
                ),
                # array: [ value (, value)* ] or []
                st.builds(
                    lambda values: "[" + ",".join(values) + "]",
                    st.lists(children, max_size=4),
                ),
            ),
            max_leaves=10,
        )

    json_text = json_value().map(lambda s: s + "\n")

    # Draw one example and encode as bytes
    s = draw(json_text)
    return s.encode("utf-8")