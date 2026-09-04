from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, '.15g'))
    # JSON strings with safe codepoints and escapes
    # We use a simplified safe string strategy that avoids control chars and quotes/backslash except escaped
    json_string = st.text(
        alphabet=(
            # safe codepoints excluding control chars, quotes, backslash
            # roughly ~[\u0020-\u10FFFF] except " and \
            # Hypothesis text defaults to unicode, so we filter out quotes and backslash
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # Forward declaration for recursive structures
    # We'll build a recursive strategy for value

    # We define a helper to build JSON values recursively with bounded depth
    def json_value():
        # Base cases: primitives
        base = st.one_of(
            json_string,
            json_number,
            json_true,
            json_false,
            json_null,
        )
        # Recursive cases: arrays and objects
        # Use st.recursive to keep size bounded
        return st.recursive(
            base,
            lambda children: st.one_of(
                # array: [value, ...]
                st.lists(children, min_size=0, max_size=5).map(
                    lambda vs: "[" + ",".join(vs) + "]"
                ),
                # object: {"key": value, ...}
                st.dictionaries(
                    keys=st.text(
                        alphabet=st.characters(
                            blacklist_characters=['"', '\\'],
                            min_codepoint=0x20,
                            max_codepoint=0x10FFFF,
                        ),
                        min_size=1,
                        max_size=10,
                    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'),
                    values=children,
                    min_size=0,
                    max_size=5,
                ).map(
                    lambda d: "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"
                ),
            ),
            max_leaves=10,
        )

    val = draw(json_value())
    return val.encode("utf-8")