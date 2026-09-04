from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly follow grammar, but keep it simple and safe
    # We'll generate strings without control chars, backslash, or quotes inside
    def json_string():
        # SAFECODEPOINT: ~["\\\u0000-\u001F]
        # We'll generate unicode codepoints excluding control chars and quotes/backslash
        # Use ascii letters, digits, punctuation except " and \
        safe_chars = (
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # Limit length to keep size bounded
        return st.text(safe_chars, min_size=0, max_size=20).map(lambda s: '"' + s + '"')

    # NUMBER: follow grammar roughly
    # We'll generate floats and ints as strings
    def json_number():
        # Use floats and ints, then convert to string
        # Limit magnitude to keep output small
        return st.one_of(
            st.integers(min_value=-10**6, max_value=10**6).map(str),
            st.floats(
                allow_nan=False,
                allow_infinity=False,
                width=32,
                min_value=-1e6,
                max_value=1e6,
            ).map(lambda f: format(f, '.6g')),
        )

    # Forward declare value strategy to allow recursion
    # We'll use st.recursive to build nested objects and arrays

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string(),
        json_number(),
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: object and array
    # pair: STRING ':' value
    # obj: '{' pair (',' pair)* '}' | '{}'
    # arr: '[' value (',' value)* ']' | '[]'

    def json_pair():
        # pair: STRING ':' value
        key = json_string()
        # value is recursive, so use the outer value strategy
        return st.tuples(key, value).map(lambda kv: kv[0] + ":" + kv[1])

    def json_obj():
        # empty or with pairs
        # limit number of pairs to keep size bounded
        pairs = st.lists(json_pair(), max_size=5)
        return st.one_of(
            st.just("{}"),
            pairs.map(lambda ps: "{" + ",".join(ps) + "}"),
        )

    def json_arr():
        # empty or with values
        values = st.lists(value, max_size=5)
        return st.one_of(
            st.just("[]"),
            values.map(lambda vs: "[" + ",".join(vs) + "]"),
        )

    # Compose recursive value strategy
    value = st.recursive(
        base_values,
        lambda children: st.one_of(json_obj(), json_arr()),
        max_leaves=10,
    )

    # Draw a value and encode as bytes
    s = draw(value)
    return s.encode("utf-8")