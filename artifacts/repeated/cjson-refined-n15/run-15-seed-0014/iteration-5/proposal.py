from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives as strings
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes
    # Use Hypothesis built-in json string strategy for correctness
    json_string = st.text(
        alphabet=(
            # safe codepoints excluding control chars and quotes/backslash
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # NUMBER strategy: produce valid JSON numbers as strings
    # Use floats and ints converted to strings with JSON-compatible formatting
    def number_to_json(n):
        # Format int or float to JSON number string
        if isinstance(n, int):
            return str(n)
        else:
            # Use repr to preserve exponent notation if any
            return repr(n)

    json_number = st.one_of(
        st.integers(min_value=-10**6, max_value=10**6).map(number_to_json),
        st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ).map(number_to_json),
    )

    # Recursive JSON value strategy
    # Use bounded recursion depth and size to keep examples small
    def json_value():
        # Compose the recursive strategy lazily
        return st.recursive(
            base=st.one_of(json_null, json_true, json_false, json_string, json_number),
            extend=lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.builds(
                    lambda pairs: "{" + ",".join(pairs) + "}",
                    st.lists(
                        st.tuples(
                            json_string,
                            children,
                        ).map(lambda t: f"{t[0]}:{t[1]}"),
                        max_size=3,
                    ),
                ),
                # array: [ value (, value)* ] or []
                st.builds(
                    lambda values: "[" + ",".join(values) + "]",
                    st.lists(children, max_size=3),
                ),
            ),
            max_leaves=10,
        )

    s = json_value()

    # Draw a JSON string and encode to bytes
    js = draw(s)
    return js.encode("utf-8")