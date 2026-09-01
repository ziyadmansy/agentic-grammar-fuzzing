from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.from_regex(
        r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?",
        fullmatch=True,
    )
    # STRING: roughly match JSON string content with escapes and safe codepoints
    # We'll generate Python strings and then json.dumps them to ensure correctness.
    # But since we can't import json here, we approximate with a safe string strategy.
    # We'll generate strings without control chars or unescaped quotes/backslashes.
    # Then we add quotes around them and escape backslashes and quotes.
    def json_string():
        # safe characters: no control chars, no " or \ (must be escaped)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # generate strings up to length 20 to keep size bounded
        s = draw(st.text(safe_chars, max_size=20))
        # escape backslash and quote if any (should be none)
        # but just in case, replace them
        s = s.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{s}"'

    # We cannot call draw inside a nested strategy, so we define a recursive strategy
    # using st.recursive with base strategies and recursive combinators.

    base = st.one_of(
        st.just("null"),
        st.just("true"),
        st.just("false"),
        json_number,
        st.deferred(lambda: st.just(json_string())),
    )

    # Recursive strategy for arrays and objects
    def json_value():
        return st.recursive(
            base,
            lambda children: st.one_of(
                # array: [value, value, ...]
                st.lists(children, max_size=3).map(lambda vs: "[" + ",".join(vs) + "]"),
                # object: {"key": value, ...}
                st.dictionaries(
                    st.text(
                        st.characters(
                            blacklist_characters=['"', '\\', '\u0000', '\u001F'],
                            min_codepoint=0x20,
                            max_codepoint=0x10FFFF,
                        ),
                        max_size=10,
                    ).map(lambda k: k.replace('\\', '\\\\').replace('"', '\\"')),
                    children,
                    max_size=3,
                ).map(
                    lambda d: "{" + ",".join(f'"{k}":{v}' for k, v in d.items()) + "}"
                    if d
                    else "{}"
                ),
            ),
            max_leaves=10,
        )

    val = draw(json_value())
    return val.encode("utf-8")