from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then JSON-encode them to ensure correctness.
    # But since we can't import json or use eval, we build strings manually.
    # Instead, use st.text with safe characters and escape some chars manually.

    # Allowed safe codepoints: all except control chars and " and \
    # We'll generate text excluding control chars and " and \, then escape " and \ manually.
    def json_string():
        # Characters allowed unescaped inside JSON strings:
        # Unicode codepoints except control chars (0x00-0x1F), " and \
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # Control chars
        )
        # Generate text of length 0 to 20
        s = draw(st.text(safe_chars, min_size=0, max_size=20))
        # Escape backslash and quote manually
        s_escaped = s.replace('\\', '\\\\').replace('"', '\\"')
        # Also escape control chars if any slipped in (shouldn't)
        # But we excluded control chars, so safe.
        return '"' + s_escaped + '"'

    # NUMBER strategy: produce valid JSON numbers as strings
    def json_number():
        # Use Hypothesis floats and convert to JSON number strings
        # But floats can produce inf/nan which are invalid JSON numbers
        # So generate decimal strings manually
        # Use st.floats with allow_infinity=False, allow_nan=False, width=16
        # Then format with repr or str, but repr can produce scientific notation
        # JSON allows scientific notation, so it's fine.
        f = draw(
            st.floats(
                allow_infinity=False,
                allow_nan=False,
                width=16,
                min_value=-1e10,
                max_value=1e10,
            )
        )
        # Format float to JSON number string
        # Use repr to keep scientific notation if needed
        s = repr(f)
        # repr can produce 'inf' or 'nan' if allow_infinity or allow_nan were True, but we disabled
        # Also, repr(-0.0) -> '-0.0' which is valid JSON
        return s

    # Recursive strategy for JSON values
    # We'll define a recursive strategy for value strings (not Python objects)
    # to produce valid JSON text for values.

    # Forward declaration for value
    # We'll define a function to build the recursive strategy
    def json_value():
        # Base cases: string, number, true, false, null
        base = st.deferred(lambda: st.one_of(
            st.builds(lambda s: s, st.just(json_string())),
            st.builds(lambda n: n, st.just(json_number())),
            json_true,
            json_false,
            json_null,
        ))

        # Recursive cases: object and array
        # To keep size bounded, limit max depth and max elements
        max_depth = 3
        max_pairs = 4
        max_elements = 4

        def obj_strategy(depth):
            if depth <= 0:
                # Empty object only
                return st.just("{}")
            else:
                # pair: STRING ':' value
                # STRING keys: reuse json_string()
                # value: recursive call with depth-1
                pair = st.tuples(
                    st.just(json_string()),
                    json_value_depth(depth - 1)
                ).map(lambda kv: f"{kv[0]}:{kv[1]}")

                pairs = st.lists(pair, max_size=max_pairs)
                return pairs.map(
                    lambda ps: "{" + ",".join(ps) + "}" if ps else "{}"
                )

        def arr_strategy(depth):
            if depth <= 0:
                return st.just("[]")
            else:
                elements = st.lists(json_value_depth(depth - 1), max_size=max_elements)
                return elements.map(
                    lambda es: "[" + ",".join(es) + "]" if es else "[]"
                )

        def json_value_depth(depth):
            return st.one_of(
                base,
                obj_strategy(depth),
                arr_strategy(depth),
            )

        return json_value_depth(max_depth)

    # Generate the full JSON text: value + EOF
    json_text = draw(json_value())

    # Return bytes
    return json_text.encode("utf-8")