from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly matching the grammar, allowing escapes and safe codepoints
    # We'll generate Python strings and then json-encode them for safety.
    # But since we can't import json, we do a simple escape for quotes and backslashes.
    def json_string(s: str) -> str:
        # Escape backslash and double quote and control chars minimally
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        # Replace control chars with \uXXXX
        def esc_char(c):
            if ord(c) < 0x20:
                return "\\u%04x" % ord(c)
            return c
        s = "".join(esc_char(c) for c in s)
        return f'"{s}"'

    # STRING strategy: generate unicode strings without control chars (except we escape them)
    # Limit length to keep size bounded
    safe_char = st.characters(
        blacklist_characters=['"', '\\'],
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    )
    string_strat = st.text(safe_char, min_size=0, max_size=20).map(json_string)

    # NUMBER: generate numbers as strings matching the grammar
    # We'll generate floats and ints and convert to strings accordingly
    def number_to_str(n):
        # Format int or float to JSON number string
        if isinstance(n, int):
            return str(n)
        else:
            # Use repr to get a JSON-compatible float string
            s = repr(n)
            # Ensure exponent E is uppercase
            s = s.replace("e", "E")
            return s

    number_strat = st.one_of(
        st.integers(min_value=-10**6, max_value=10**6).map(number_to_str),
        st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ).map(number_to_str),
    )

    # Forward declaration for recursive structures
    # We'll define value_strat recursively below

    # Pair: STRING ':' value
    @st.composite
    def pair(draw):
        k = draw(string_strat)
        v = draw(value_strat)
        return f"{k}:{v}"

    # Object: '{' pair (',' pair)* '}' or '{}'
    @st.composite
    def obj(draw):
        # Limit number of pairs to keep size bounded
        pairs = draw(st.lists(pair(), min_size=0, max_size=5))
        if not pairs:
            return "{}"
        return "{" + ",".join(pairs) + "}"

    # Array: '[' value (',' value)* ']' or '[]'
    @st.composite
    def arr(draw):
        values = draw(st.lists(value_strat, min_size=0, max_size=5))
        if not values:
            return "[]"
        return "[" + ",".join(values) + "]"

    # Now define value_strat recursively
    # We use st.recursive to keep recursion bounded
    base = st.one_of(
        string_strat,
        number_strat,
        json_null,
        json_true,
        json_false,
    )

    # We need to define value_strat as a recursive strategy
    # But pair, obj, arr depend on value_strat, so we use a trick:
    # define value_strat as a placeholder, then assign it below.

    # Placeholder for value_strat
    value_strat = st.deferred(lambda: value_strat)

    # Now define value_strat properly using st.recursive
    value_strat = st.recursive(
        base,
        lambda children: st.one_of(
            obj(),
            arr(),
        ),
        max_leaves=10,
    )

    # Finally, generate the full JSON text and encode as bytes
    json_text = draw(value_strat)
    return json_text.encode("utf-8")