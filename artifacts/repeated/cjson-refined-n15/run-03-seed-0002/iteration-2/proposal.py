from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, '.15g'))
    # JSON strings with safe codepoints and escapes
    json_string = st.text(
        alphabet=(
            # safe codepoints excluding control chars and " \ 
            ''.join(chr(c) for c in range(0x20, 0x7F) if c not in (0x22, 0x5C))
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # Recursive JSON values: string, number, obj, arr, true, false, null
    # Use bounded recursion to keep sizes manageable
    def json_value():
        return st.recursive(
            base=st.one_of(json_string, json_number, json_true, json_false, json_null),
            extend=lambda children: st.one_of(
                json_object(children),
                json_array(children),
            ),
            max_leaves=10,
        )

    # JSON pair: STRING : value
    @st.composite
    def json_pair(draw, val_strat):
        key = draw(json_string)
        val = draw(val_strat)
        return f"{key}:{val}"

    # JSON object: { pair (, pair)* } or {}
    @st.composite
    def json_object(draw, val_strat):
        # limit pairs to max 5 to keep size bounded
        pairs = draw(st.lists(json_pair(val_strat), max_size=5))
        if not pairs:
            return "{}"
        return "{" + ",".join(pairs) + "}"

    # JSON array: [ value (, value)* ] or []
    @st.composite
    def json_array(draw, val_strat):
        vals = draw(st.lists(val_strat, max_size=5))
        if not vals:
            return "[]"
        return "[" + ",".join(vals) + "]"

    # Compose the full json strategy
    val_strat = json_value()
    json_text = draw(val_strat)
    return json_text.encode("utf-8")