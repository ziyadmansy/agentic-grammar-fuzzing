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
    # STRING: roughly valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then JSON-encode them to ensure correctness
    # but since we can't import json or use eval, we build strings manually.
    # We'll generate strings with safe characters and some escapes.
    def json_string():
        # safe codepoints excluding control chars and " and \
        safe_chars = (
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # some escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # build a string of length 0 to 20 with mix of safe chars and escapes
        pieces = st.lists(st.one_of(safe_chars.map(lambda c: c), escapes), max_size=20)
        return pieces.map(lambda chars: '"' + "".join(chars) + '"')

    json_string_st = json_string()

    # Recursive strategy for value
    # We'll limit recursion depth and size to keep campaign bounded
    def json_value():
        return st.recursive(
            st.one_of(
                json_string_st,
                json_number,
                json_true,
                json_false,
                json_null,
            ),
            lambda children: st.one_of(
                # obj: '{' pair (',' pair)* '}' | '{}'
                st.builds(
                    lambda pairs: "{" + ",".join(pairs) + "}",
                    st.lists(
                        st.tuples(
                            json_string_st,
                            children,
                        ).map(lambda p: f"{p[0]}:{p[1]}"),
                        max_size=3,
                    ),
                ),
                st.just("{}"),
                # arr: '[' value (',' value)* ']' | '[]'
                st.builds(
                    lambda values: "[" + ",".join(values) + "]",
                    st.lists(children, max_size=3),
                ),
                st.just("[]"),
            ),
            max_leaves=10,
        )

    val = draw(json_value())
    return val.encode("utf-8")