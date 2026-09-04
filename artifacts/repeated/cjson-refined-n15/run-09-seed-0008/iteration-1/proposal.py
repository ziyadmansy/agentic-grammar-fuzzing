from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, '.15g'))
    # JSON strings: use safe codepoints excluding control chars and backslash, quote
    json_string = st.text(
        alphabet=(
            # all Unicode except control chars (U+0000-U+001F), backslash, and quote
            # Hypothesis text() doesn't support exclusion, so filter after generation
            # We'll generate ASCII printable except backslash and quote for simplicity
            [chr(c) for c in range(0x20, 0x7F) if c not in (0x22, 0x5C)]
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s + '"')

    # Recursive JSON value
    # We'll define a recursive strategy for value, obj, arr

    # Forward declaration for value
    # We'll define value as a recursive strategy below

    # pair: STRING ':' value
    def pair():
        return st.tuples(json_string, value).map(lambda p: p[0] + ":" + p[1])

    # obj: '{' pair (',' pair)* '}' or '{}'
    def obj():
        # up to 3 pairs to keep size bounded
        pairs = st.lists(pair(), max_size=3)
        return pairs.map(lambda ps: "{" + ",".join(ps) + "}" if ps else "{}")

    # arr: '[' value (',' value)* ']' or '[]'
    def arr():
        # up to 3 elements to keep size bounded
        elements = st.lists(value, max_size=3)
        return elements.map(lambda es: "[" + ",".join(es) + "]" if es else "[]")

    # Now define value as recursive
    value = st.deferred(lambda: st.one_of(
        json_string,
        json_number,
        obj(),
        arr(),
        json_true,
        json_false,
        json_null,
    ))

    # Compose the full json with EOF (just ensure full string)
    json_full = value

    s = draw(json_full)
    return s.encode("utf-8")