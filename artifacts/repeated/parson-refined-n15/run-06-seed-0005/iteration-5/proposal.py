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
        max_size=20,
    )
    # STRING: roughly matching the grammar, allowing escapes and safe codepoints
    # We'll generate strings and then JSON-encode them to handle escapes properly.
    # But since we can't import json or use eval, we approximate with a safe subset.
    # We'll generate strings without control chars and backslash or quote, then add escapes manually.
    safe_chars = (
        st.characters(
            blacklist_characters=['"', '\\'] + [chr(c) for c in range(0x00, 0x20)]
        )
    )
    # To include escapes, we add a small chance of escape sequences inside strings.
    def json_string():
        # Compose a string with safe chars and occasional escapes
        def escape_char():
            # Choose one escape sequence from the grammar
            esc = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
            # Or a unicode escape \uXXXX
            unicode_esc = st.builds(
                lambda h1,h2,h3,h4: f"\\u{h1}{h2}{h3}{h4}",
                st.sampled_from("0123456789abcdefABCDEF"),
                st.sampled_from("0123456789abcdefABCDEF"),
                st.sampled_from("0123456789abcdefABCDEF"),
                st.sampled_from("0123456789abcdefABCDEF"),
            )
            return st.one_of(esc, unicode_esc)
        # Build a list of chars or escapes
        # Limit length to keep size bounded
        parts = st.lists(st.one_of(safe_chars, escape_char()), max_size=20)
        return parts.map(lambda chars: '"' + "".join(chars) + '"')
    json_string = json_string()

    # Recursive JSON values
    # We'll use st.recursive to build obj and arr with bounded depth and size.
    # Base values: string, number, true, false, null
    base_values = st.one_of(json_string, json_number, json_true, json_false, json_null)

    # Forward declarations for obj and arr
    # We'll define obj and arr inside the recursive strategy

    def json_value():
        # Recursive strategy for value
        # Use st.recursive with base_values and containers
        def obj_strategy():
            # pair: STRING ':' value
            pair = st.tuples(json_string, json_value()).map(lambda p: f"{p[0]}:{p[1]}")
            # obj: '{' pair (',' pair)* '}' or '{}'
            # To keep near-valid, allow empty or non-empty objects
            return st.one_of(
                st.just("{}"),
                st.lists(pair, min_size=1, max_size=5).map(lambda pairs: "{" + ",".join(pairs) + "}"),
            )

        def arr_strategy():
            # arr: '[' value (',' value)* ']' or '[]'
            return st.one_of(
                st.just("[]"),
                st.lists(json_value(), min_size=1, max_size=5).map(lambda vals: "[" + ",".join(vals) + "]"),
            )

        # Compose recursive strategy
        return st.recursive(
            base_values,
            lambda children: st.one_of(obj_strategy(), arr_strategy()),
            max_leaves=10,
        )

    # Generate a full json text and append EOF (which is implicit)
    json_text = json_value()

    # Draw the json text string and encode to bytes
    s = draw(json_text)
    return s.encode("utf-8")