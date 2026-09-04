from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.from_regex(
        r"-?(0|[1-9]\d*)(\.\d+)?([eE][+-]?\d+)?",
        fullmatch=True,
        flags=0,
    )
    # JSON string with safe codepoints and escapes
    # We'll use Hypothesis's built-in string strategy with restrictions
    # to avoid control chars and unescaped quotes/backslashes.
    # We allow some escapes by including backslash and quotes carefully.
    # But to keep it simple and valid, we generate unicode strings excluding control chars and quotes/backslash,
    # then we quote them properly.
    json_string_content = st.text(
        alphabet=st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=20,
    )
    def json_string():
        s = draw(json_string_content)
        # Escape backslash and quote in output
        s_escaped = s.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{s_escaped}"'

    # Recursive strategy for JSON values
    # Use st.recursive to build nested arrays and objects
    base = st.one_of(
        json_null,
        json_true,
        json_false,
        json_number,
        st.deferred(json_string),
    )

    # To avoid infinite recursion and large outputs, limit max_leaves
    def json_value():
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.builds(
                    lambda pairs: "{" + ",".join(pairs) + "}",
                    st.lists(
                        st.tuples(
                            st.deferred(json_string),
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

    result = draw(json_value())
    return result.encode("utf-8")