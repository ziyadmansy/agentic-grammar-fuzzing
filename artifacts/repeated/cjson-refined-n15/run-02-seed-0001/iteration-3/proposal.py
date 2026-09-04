from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string strategy
    # SAFECODEPOINT excludes control chars and " \, so we generate safe unicode strings without control chars
    # We'll generate strings with codepoints >= 0x20 except " and \, roughly matching SAFECODEPOINT
    def json_string():
        # Characters allowed inside JSON strings (excluding " and \ and control chars)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escape sequences: \", \\, \b, \f, \n, \r, \t, \uXXXX
        # We'll generate mostly safe chars, but sometimes insert escapes
        # To keep it simple, generate strings of safe chars only
        return st.text(safe_chars, min_size=0, max_size=20).map(lambda s: '"' + s + '"')

    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, '.15g'))
    # Format floats to JSON number format, avoiding scientific notation for small integers
    # But hypothesis floats can be large or small, so allow scientific notation

    # Forward declaration for recursive structures
    # We'll use st.recursive to build nested arrays and objects

    # Pair: STRING ':' value
    @st.composite
    def json_pair(draw, value_strat):
        key = draw(json_string())
        val = draw(value_strat)
        return f"{key}:{val}"

    def json_obj(value_strat):
        # Object: {} or { pair (, pair)* }
        # Limit number of pairs to keep size bounded
        pairs = st.lists(json_pair(value_strat), max_size=5)
        return pairs.map(
            lambda ps: "{" + (",".join(ps) if ps else "") + "}"
        )

    def json_arr(value_strat):
        # Array: [] or [ value (, value)* ]
        values = st.lists(value_strat, max_size=5)
        return values.map(
            lambda vs: "[" + (",".join(vs) if vs else "") + "]"
        )

    # Recursive value strategy
    base = st.one_of(
        json_string(),
        json_number,
        json_null,
        json_true,
        json_false,
    )

    # Use recursive to build arrays and objects
    value = st.recursive(
        base,
        lambda children: st.one_of(
            json_arr(children),
            json_obj(children),
        ),
        max_leaves=10,
    )

    # Draw a full JSON value and append EOF (implicit)
    result = draw(value)
    return result.encode("utf-8")