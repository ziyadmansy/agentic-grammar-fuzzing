from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then json-encode them to ensure correctness.
    # But since we can't import json, we approximate escaping.
    # To keep it simple, generate strings without control chars or backslash/quote,
    # plus some escapes.

    # Characters allowed inside JSON strings (excluding control chars and backslash/quote)
    safe_chars = st.characters(
        blacklist_characters=['"', '\\'],
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    )

    # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
    # We'll simulate escapes by mixing safe chars and some escapes as literals.
    # To keep it simple, generate strings without escapes but valid codepoints.
    # This is near-valid but acceptable for fuzzing.

    json_string = st.text(safe_chars, max_size=20).map(lambda s: '"' + s + '"')

    # NUMBER: generate numbers as strings matching the grammar
    # We'll generate floats and ints and convert to strings
    def number_to_str(n):
        # Format number to JSON number string
        # Use repr for floats, str for ints
        if isinstance(n, int):
            return str(n)
        else:
            # repr may produce scientific notation, which is allowed
            return repr(n)

    json_number = st.one_of(
        st.integers(min_value=-10**6, max_value=10**6).map(number_to_str),
        st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ).map(number_to_str),
    )

    # Recursive JSON values: string, number, obj, arr, true, false, null
    # Use st.recursive to keep bounded recursion and size

    base = st.one_of(json_string, json_number, json_null, json_true, json_false)

    # Forward declarations for obj and arr to use in recursive
    # We'll define them inside the recursive call

    def json_value():
        return st.deferred(lambda: value)

    # pair: STRING ':' value
    pair = st.tuples(json_string, json_value()).map(lambda p: p[0] + ":" + p[1])

    # obj: '{' pair (',' pair)* '}' or '{}'
    def obj_strategy():
        # up to 3 pairs to keep size bounded
        pairs = st.lists(pair, max_size=3)
        return pairs.map(
            lambda ps: "{" + (",".join(ps) if ps else "") + "}"
        )

    # arr: '[' value (',' value)* ']' or '[]'
    def arr_strategy():
        values = st.lists(json_value(), max_size=3)
        return values.map(
            lambda vs: "[" + (",".join(vs) if vs else "") + "]"
        )

    # Now define value as recursive
    value = st.recursive(
        base,
        lambda children: st.one_of(obj_strategy(), arr_strategy()),
        max_leaves=10,
    )

    # Draw a value and encode as bytes
    s = draw(value)
    return s.encode("utf-8")