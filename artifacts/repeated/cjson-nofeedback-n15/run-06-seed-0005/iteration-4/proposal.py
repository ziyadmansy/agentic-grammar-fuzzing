from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.from_regex(
        r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?",
        fullmatch=True,
    )
    # STRING: roughly valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode as JSON strings with quotes and escapes.
    # To keep it simple, generate unicode strings excluding control chars and quotes/backslash,
    # then escape quotes and backslash manually.
    def json_string():
        # safe codepoints: exclude control chars (0x00-0x1F), quotes (0x22), backslash (0x5C)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',),
        )
        # limit length to keep size bounded
        s = draw(st.text(safe_chars, max_size=20))
        # escape backslash and quotes if any (should be none), but just in case
        s_escaped = s.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{s_escaped}"'

    # We'll build recursive JSON values using st.recursive
    # Base: string, number, true, false, null
    base = st.one_of(
        st.builds(lambda s: s, st.deferred(lambda: st.just(json_string()))),
        json_number,
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: object and array
    # To keep output bounded, limit size of arrays and objects
    def json_value():
        return st.deferred(lambda: value)

    # pair: STRING ':' value
    def json_pair():
        key = st.text(
            st.characters(
                blacklist_characters=['"', '\\'],
                blacklist_categories=('Cc',),
            ),
            max_size=10,
        ).map(lambda s: f'"{s}"')
        val = json_value()
        return st.tuples(key, val).map(lambda kv: f"{kv[0]}:{kv[1]}")

    json_object = st.lists(json_pair(), max_size=5).map(
        lambda pairs: "{" + ",".join(pairs) + "}"
    )

    json_array = st.lists(json_value(), max_size=5).map(
        lambda values: "[" + ",".join(values) + "]"
    )

    value = st.recursive(
        base,
        lambda children: st.one_of(json_object, json_array),
        max_leaves=10,
    )

    # Draw the final JSON string
    s = draw(value)
    return s.encode("utf-8")