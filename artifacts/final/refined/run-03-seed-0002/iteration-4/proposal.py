from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly matching grammar, allowing escapes and safe codepoints
    # We'll generate Python strings and then JSON-encode them with repr or json.dumps
    # but since we can't import json, we'll build a simple encoder here.
    # To keep it simple, generate strings without control chars and escape quotes and backslashes.
    def json_string(s: str) -> str:
        # Escape backslash and quote
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        # Escape control chars (U+0000 to U+001F) as \uXXXX
        def esc_char(c):
            if ord(c) < 0x20:
                return "\\u%04x" % ord(c)
            return c
        s = "".join(esc_char(c) for c in s)
        return f'"{s}"'

    # STRING strategy: generate unicode strings excluding control chars and quotes/backslash
    # We'll allow some escapes by including backslash and quote but escaping them.
    # To keep it simple, exclude control chars and generate from safe codepoints.
    safe_chars = st.characters(
        blacklist_characters=['"', '\\'],
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    )
    json_string_strat = st.text(safe_chars, min_size=0, max_size=20).map(json_string)

    # NUMBER: generate valid JSON numbers as strings
    # Use floats and ints, then convert to string with JSON-compatible formatting
    def json_number(n):
        # Format int or float to JSON number string
        if isinstance(n, int):
            return str(n)
        else:
            # Use repr to get exponent notation if needed
            s = repr(n)
            # JSON requires lowercase e
            s = s.replace("E", "e")
            # Remove trailing + in exponent if any
            s = s.replace("+", "")
            return s

    json_number_strat = st.one_of(
        st.integers(min_value=-(10**9), max_value=10**9).map(json_number),
        st.floats(
            allow_infinity=False,
            allow_nan=False,
            width=32,
            min_value=-1e9,
            max_value=1e9,
        ).map(json_number),
    )

    # Recursive value strategy
    # We'll define a recursive strategy for value that includes:
    # STRING, NUMBER, obj, arr, true, false, null

    # Forward declaration for value
    # Use st.deferred to allow recursion
    @st.composite
    def json_value(draw):
        # Base cases: primitives
        base = st.one_of(
            json_string_strat,
            json_number_strat,
            json_true,
            json_false,
            json_null,
        )
        # Recursive cases: obj and arr
        # Limit recursion depth by max_leaves
        # We'll use bounded recursion with max_leaves=5 to keep size manageable
        def json_obj():
            # pair: STRING ':' value
            # Generate 0 to 5 pairs
            pairs = st.lists(
                st.tuples(json_string_strat, json_value()),
                min_size=0,
                max_size=5,
                unique_by=lambda p: p[0],  # unique keys
            )
            def render_obj(pairs):
                if not pairs:
                    return "{}"
                inner = ",".join(f"{k}:{v}" for k, v in pairs)
                return "{" + inner + "}"
            return pairs.map(render_obj)

        def json_arr():
            # Generate 0 to 5 values
            arr_vals = st.lists(json_value(), min_size=0, max_size=5)
            def render_arr(vals):
                if not vals:
                    return "[]"
                return "[" + ",".join(vals) + "]"
            return arr_vals.map(render_arr)

        # Compose recursive strategy
        rec = st.deferred(lambda: st.one_of(base, json_obj(), json_arr()))
        # Draw one value from recursive strategy
        return draw(rec)

    # Draw the full JSON value and append EOF (nothing)
    val = draw(json_value())
    # Return as bytes
    return val.encode("utf-8")