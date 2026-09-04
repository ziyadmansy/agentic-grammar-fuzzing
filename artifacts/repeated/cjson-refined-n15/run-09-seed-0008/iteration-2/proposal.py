from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy matching JSON STRING grammar roughly
    # Use repr to produce JSON string escapes safely
    def json_string():
        # Use ascii characters excluding control chars and backslash, quote
        # Hypothesis text with safe codepoints, then json-escape them
        # We'll generate Python strings and then encode as JSON strings
        # but to keep it simple, use st.text with safe chars and then json.dumps
        import json
        s = draw(
            st.text(
                alphabet=(
                    # safe codepoints: exclude control chars (<=0x1F), backslash, quote
                    st.characters(
                        blacklist_characters=['\\', '"'],
                        min_codepoint=0x20,
                        max_codepoint=0x10FFFF,
                    )
                ),
                min_size=0,
                max_size=20,
            )
        )
        return json.dumps(s)

    json_string_st = st.deferred(json_string)

    # NUMBER strategy matching JSON NUMBER grammar roughly
    # Use floats and ints, then convert to JSON number strings
    def json_number():
        # Generate floats and ints in reasonable range, then convert to string
        # Use floats with limited decimal places to keep output small
        n = draw(
            st.one_of(
                st.integers(min_value=-10**6, max_value=10**6),
                st.floats(
                    allow_nan=False,
                    allow_infinity=False,
                    width=32,
                    min_value=-10**6,
                    max_value=10**6,
                ),
            )
        )
        # Format as JSON number string
        if isinstance(n, int):
            return str(n)
        else:
            # Use repr to get a JSON-compatible float string (no inf/nan)
            return repr(n)

    json_number_st = st.deferred(json_number)

    # Recursive JSON value strategy
    # Use st.recursive to build nested objects and arrays with bounded depth and size
    base = st.one_of(
        json_string_st,
        json_number_st,
        json_null,
        json_true,
        json_false,
    )

    # Pair: STRING ':' value
    @st.composite
    def pair(draw):
        k = draw(json_string_st)
        v = draw(value)
        return f"{k}:{v}"

    # Object: '{' pair (',' pair)* '}' or '{}'
    @st.composite
    def obj(draw):
        # Limit number of pairs to keep size bounded
        pairs = draw(st.lists(pair(), min_size=0, max_size=5))
        if pairs:
            return "{" + ",".join(pairs) + "}"
        else:
            return "{}"

    # Array: '[' value (',' value)* ']' or '[]'
    @st.composite
    def arr(draw):
        values = draw(st.lists(value, min_size=0, max_size=5))
        if values:
            return "[" + ",".join(values) + "]"
        else:
            return "[]"

    # Recursive value strategy including obj and arr
    value = st.recursive(
        base,
        lambda children: st.one_of(obj(), arr()),
        max_leaves=10,
    )

    # Draw a full JSON text and encode as bytes
    json_text = draw(value)
    return json_text.encode("utf-8")