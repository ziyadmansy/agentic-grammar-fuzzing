from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: use Hypothesis text with safe codepoints, escape as needed
    def json_string():
        # Use characters excluding control chars and " and \
        # SAFECODEPOINT: ~["\\\u0000-\u001F]
        # We'll generate unicode strings excluding control chars and quotes/backslash
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Limit length to keep size bounded
        return st.text(safe_chars, min_size=0, max_size=20).map(
            lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
        )

    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: str(f))

    # Forward declaration for recursive structures
    # We'll use st.recursive to build obj and arr

    # Pair: STRING ':' value
    @st.composite
    def pair(draw, value_strat):
        k = draw(json_string())
        v = draw(value_strat)
        return f"{k}:{v}"

    # obj: '{' pair (',' pair)* '}' | '{}'
    def json_obj(value_strat):
        # pairs: 0 to 5 pairs to keep size bounded
        pairs = st.lists(pair(value_strat), max_size=5)
        return pairs.map(
            lambda ps: "{" + ",".join(ps) + "}" if ps else "{}"
        )

    # arr: '[' value (',' value)* ']' | '[]'
    def json_arr(value_strat):
        values = st.lists(value_strat, max_size=5)
        return values.map(
            lambda vs: "[" + ",".join(vs) + "]" if vs else "[]"
        )

    # Recursive value strategy
    base = st.one_of(
        json_string(),
        json_number,
        json_null,
        json_true,
        json_false,
    )

    # Use st.recursive to add obj and arr
    value = st.recursive(
        base,
        lambda children: st.one_of(
            json_obj(children),
            json_arr(children),
        ),
        max_leaves=10,
    )

    result = draw(value)
    return result.encode("utf-8")