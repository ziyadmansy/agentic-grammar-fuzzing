from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # JSON strings: use safe unicode codepoints excluding control chars and quotes/backslash
    json_string = st.text(
        alphabet=(
            # exclude control chars (<= 0x1F), quote (0x22), backslash (0x5C)
            # allow all other unicode codepoints except surrogates
            # Hypothesis text() by default excludes surrogates
            # We'll filter out control chars and forbidden chars
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s + '"')

    # Forward declare value strategy for recursion
    # Use recursive to keep bounded size and depth
    def json_value():
        return st.deferred(lambda: json_value_strategy)

    # Compose object and array strategies
    json_pair = st.tuples(json_string, json_value()).map(lambda kv: f"{kv[0]}:{kv[1]}")

    json_obj = st.lists(json_pair, max_size=5).map(
        lambda pairs: "{" + (",".join(pairs) if pairs else "") + "}"
    )

    json_arr = st.lists(json_value(), max_size=5).map(
        lambda values: "[" + (",".join(values) if values else "") + "]"
    )

    json_value_strategy = st.recursive(
        base=st.one_of(json_string, json_number, json_null, json_true, json_false),
        extend=lambda children: st.one_of(json_obj, json_arr),
        max_leaves=10,
    )

    # Compose full JSON with EOF (no trailing data)
    json_full = json_value_strategy.map(lambda v: v)

    s = draw(json_full)
    return s.encode("utf-8")