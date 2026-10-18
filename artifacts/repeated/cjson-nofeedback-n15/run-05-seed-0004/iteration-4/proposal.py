from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode them as JSON strings.
    # To keep it simple, use Hypothesis's built-in json string strategy and tweak it.
    json_string = st.text(
        st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # NUMBER strategy: generate valid JSON numbers as strings
    # Use floats and ints converted to strings, but restrict size
    json_number = st.one_of(
        st.integers(min_value=-10**6, max_value=10**6).map(str),
        st.floats(min_value=-1e6, max_value=1e6, allow_infinity=False, allow_nan=False).map(lambda f: format(f, 'g')),
    )

    # Recursive strategy for JSON values
    # We'll define a recursive function to generate values, arrays, and objects
    def json_value():
        # Base cases: primitives
        base = st.one_of(
            json_string,
            json_number,
            json_null,
            json_true,
            json_false,
        )
        # Recursive cases: arrays and objects
        return st.recursive(
            base,
            lambda children: st.one_of(
                # array: [ value (, value)* ]
                st.lists(children, max_size=3).map(
                    lambda vs: "[" + ",".join(vs) + "]"
                ),
                # object: { pair (, pair)* } or empty {}
                st.dictionaries(
                    keys=st.text(
                        st.characters(
                            blacklist_characters=['"', '\\'],
                            min_codepoint=0x20,
                            max_codepoint=0x10FFFF,
                        ),
                        max_size=10,
                    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'),
                    values=children,
                    max_size=3,
                ).map(
                    lambda d: "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"
                ),
            ),
            max_leaves=10,
        )

    result = draw(json_value())
    return result.encode("utf-8")