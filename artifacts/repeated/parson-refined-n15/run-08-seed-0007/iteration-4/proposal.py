from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: use Hypothesis built-in json string strategy
    json_string = st.text(
        alphabet=(
            # safe codepoints excluding control chars and backslash, quote
            # Hypothesis's json module uses a similar approach internally
            # We'll allow any printable except control chars and quotes/backslash
            # to keep valid JSON strings
            st.characters(
                blacklist_characters=['\\', '"'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('"', '\\"').replace('\\', '\\\\') + '"')

    # NUMBER: use Hypothesis floats converted to JSON number strings
    # Restrict to finite floats, no NaN or inf
    json_number = st.floats(
        allow_nan=False,
        allow_infinity=False,
        width=32,
        min_value=-1e10,
        max_value=1e10,
    ).map(lambda f: format(f, '.15g'))

    # Recursive strategy for JSON values
    def json_values():
        base = st.one_of(
            json_string,
            json_number,
            json_null,
            json_true,
            json_false,
        )
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: {"pair", ...}
                st.dictionaries(
                    keys=json_string,
                    values=children,
                    min_size=0,
                    max_size=5,
                ).map(lambda d: "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"),
                # array: [value, ...]
                st.lists(children, min_size=0, max_size=5).map(
                    lambda l: "[" + ",".join(l) + "]"
                ),
            ),
            max_leaves=10,
        )

    s = json_values()
    js = draw(s)
    return js.encode("utf-8")