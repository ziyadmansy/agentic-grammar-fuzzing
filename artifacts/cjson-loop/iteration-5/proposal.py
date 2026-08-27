from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # JSON strings: use Hypothesis strings filtered to exclude control chars and quotes/backslash
    json_string = st.text(
        alphabet=(
            # Unicode code points except control chars (U+0000-U+001F), quotes, and backslash
            # We exclude control chars and the characters that must be escaped in JSON strings
            # This is a simplification; Hypothesis strings are unicode, so we filter out unwanted chars
            # We'll allow all printable except " and \ and control chars
            st.characters(
                blacklist_characters=['"', '\\'],
                blacklist_categories=('Cc',)  # Cc = control chars
            )
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s + '"')

    # Recursive definition for JSON values
    # We limit max_leaves to keep size bounded and avoid too deep recursion
    json_value = st.recursive(
        base=st.one_of(json_string, json_number, json_null, json_true, json_false),
        extend=lambda children: st.one_of(
            # Object: { pair (, pair)* } or {}
            st.dictionaries(
                keys=json_string,
                values=children,
                min_size=0,
                max_size=5,
            ).map(lambda d: "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"),
            # Array: [ value (, value)* ] or []
            st.lists(children, min_size=0, max_size=5).map(lambda l: "[" + ",".join(l) + "]"),
        ),
        max_leaves=20,
    )

    # Compose full JSON with EOF
    json_text = json_value

    s = draw(json_text)
    return s.encode("utf-8")