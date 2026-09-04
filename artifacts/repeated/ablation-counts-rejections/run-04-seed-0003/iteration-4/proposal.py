from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string: use Hypothesis's built-in json string strategy, but restrict control chars
    json_string = st.text(
        alphabet=(
            # All Unicode codepoints except control chars and backslash and quote
            st.characters(
                blacklist_characters=['\\', '"'],
                blacklist_categories=('Cc',),
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('"', '\\"').replace('\\', '\\\\') + '"')

    # JSON number: use Hypothesis floats and ints, then convert to JSON number string
    def json_number_str(n):
        # Format number as JSON number string
        # Use repr for floats to get compact form
        if isinstance(n, int):
            return str(n)
        else:
            # For floats, ensure no trailing .0 if possible
            s = repr(n)
            # JSON allows exponentials, so repr is fine
            return s

    json_number = st.one_of(
        st.integers(min_value=-(10**9), max_value=10**9).map(json_number_str),
        st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e9,
            max_value=1e9,
        ).map(json_number_str),
    )

    # Forward declare value strategy to allow recursion
    # Use st.recursive to build arrays and objects

    # Base values: string, number, true, false, null
    base = st.one_of(json_string, json_number, json_true, json_false, json_null)

    # Pair: STRING ':' value
    @st.composite
    def pair(draw):
        key = draw(json_string)
        val = draw(value)
        return f"{key}:{val}"

    # Recursive value strategy
    def json_array():
        return st.lists(value, min_size=0, max_size=3).map(lambda vs: "[" + ",".join(vs) + "]")

    def json_object():
        return st.lists(pair(), min_size=0, max_size=3).map(lambda ps: "{" + ",".join(ps) + "}")

    value = st.recursive(
        base,
        lambda children: st.one_of(json_array(), json_object()),
        max_leaves=10,
    )

    # Compose full JSON: value + EOF
    json_text = value

    s = draw(json_text)
    return s.encode("utf-8")