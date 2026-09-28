from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: use Hypothesis built-in json string strategy for safety
    json_string = st.text(
        alphabet=(
            # safe unicode codepoints excluding control chars and quotes/backslash
            st.characters(
                blacklist_characters=['"', '\\'],
                blacklist_categories=('Cc',),
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # NUMBER strategy: generate numbers as strings matching JSON number grammar
    json_number = st.one_of(
        st.integers(min_value=-1_000_000, max_value=1_000_000).map(str),
        st.floats(allow_nan=False, allow_infinity=False, width=32).map(lambda f: format(f, 'g')),
    )

    # Recursive strategy for JSON values
    def json_value():
        # Use recursive to build nested arrays and objects
        base = st.one_of(json_string, json_number, json_null, json_true, json_false)
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string,
                    values=children,
                    min_size=0,
                    max_size=3,
                ).map(lambda d: (
                    "{" + 
                    ",".join(f"{k}:{v}" for k, v in d.items()) + 
                    "}"
                )),
                # array: [ value (, value)* ] or []
                st.lists(children, min_size=0, max_size=3).map(lambda l: (
                    "[" + ",".join(l) + "]"
                )),
            ),
            max_leaves=10,
        )

    # Draw a JSON value string and encode as bytes
    json_str = draw(json_value())
    return json_str.encode("utf-8")