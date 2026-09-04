from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, '.15g'))
    # JSON strings: use Hypothesis text with safe codepoints, escape quotes and backslashes
    def json_string():
        # Use a limited safe subset of unicode excluding control chars and quotes/backslash
        # SAFECODEPOINT ~["\\\u0000-\u001F]
        safe_chars = (
            st.characters(
                blacklist_characters=['\\', '"'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # Compose string with escapes for quotes and backslash
        # We'll produce a string and then escape quotes and backslash
        @st.composite
        def escaped_string(draw):
            s = draw(st.text(safe_chars, max_size=20))
            # Escape backslash and quote
            s = s.replace('\\', '\\\\').replace('"', '\\"')
            return f'"{s}"'
        return escaped_string()

    json_str = json_string()

    # Recursive JSON values: obj, arr, or primitives
    # To keep size bounded, limit max_depth and max_size

    # Forward declaration for recursive use
    def json_value():
        return st.deferred(lambda: json_value_inner())

    # Object: '{' pair (',' pair)* '}' or '{}'
    @st.composite
    def json_obj(draw):
        # pairs: STRING ':' value
        # limit number of pairs to keep size bounded
        n = draw(st.integers(min_value=0, max_value=4))
        pairs = []
        for _ in range(n):
            k = draw(json_string())
            v = draw(json_value())
            pairs.append(f"{k}:{v}")
        if pairs:
            return "{" + ",".join(pairs) + "}"
        else:
            return "{}"

    # Array: '[' value (',' value)* ']' or '[]'
    @st.composite
    def json_arr(draw):
        n = draw(st.integers(min_value=0, max_value=4))
        values = [draw(json_value()) for _ in range(n)]
        if values:
            return "[" + ",".join(values) + "]"
        else:
            return "[]"

    def json_value_inner():
        # Weighted choice to preserve variety and near-valid cases
        # Include some near-valid by mixing in some invalid escapes or truncated strings
        base = st.one_of(
            json_str,
            json_number,
            json_obj(),
            json_arr(),
            json_true,
            json_false,
            json_null,
        )
        # To preserve near-valid, sometimes produce slightly malformed strings or numbers
        # But since campaign shows 0 unique rejections, keep mostly valid
        return base

    # Compose full JSON: value + EOF
    json_text = json_value()

    s = draw(json_text)
    return s.encode("utf-8")