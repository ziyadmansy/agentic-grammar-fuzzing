from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string: use safe unicode codepoints excluding control chars and quotes/backslash
    # We use st.text with a whitelist of characters to approximate SAFECODEPOINT
    # SAFECODEPOINT excludes control chars (U+0000-U+001F), quote, backslash
    safe_chars = (
        st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
    )
    json_string = st.text(safe_chars, min_size=0, max_size=20).map(lambda s: '"' + s + '"')

    # JSON number: use Hypothesis floats converted to JSON number strings
    # Limit range and precision to keep sizes small and valid
    def number_to_json(n: float) -> str:
        # Format float to JSON number string without trailing .0 if integer
        if n == float('inf') or n == float('-inf') or n != n:
            # Avoid infinities and NaN
            return "0"
        if int(n) == n:
            return str(int(n))
        else:
            # Limit to 6 decimal places
            return format(n, '.6g')

    json_number = st.floats(
        allow_nan=False,
        allow_infinity=False,
        width=32,
        min_value=-1e6,
        max_value=1e6,
    ).map(number_to_json)

    # Forward declare value strategy for recursion
    # Use st.recursive to build nested arrays and objects
    base = st.one_of(json_string, json_number, json_null, json_true, json_false)

    # Recursive containers: arrays and objects
    # Arrays: [value, value, ...] or []
    # Objects: {"key": value, ...} or {}

    # For keys in objects, use json_string (already quoted strings)
    # For values, use the recursive value strategy

    def arrays_and_objects(children):
        json_array = st.lists(children, max_size=3).map(
            lambda vs: "[" + ",".join(vs) + "]"
        )
        json_pair = st.tuples(json_string, children).map(
            lambda kv: f"{kv[0]}:{kv[1]}"
        )
        json_object = st.lists(json_pair, max_size=3).map(
            lambda pairs: "{" + ",".join(pairs) + "}"
        )
        return st.one_of(json_array, json_object)

    json_value = st.recursive(base, arrays_and_objects, max_leaves=10)

    # Draw the final JSON string and encode as bytes
    s = draw(json_value)
    return s.encode("utf-8")