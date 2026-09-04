from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string with safe codepoints and escapes
    # We limit length to keep sizes bounded
    json_string = st.text(
        alphabet=(
            # safe codepoints excluding control chars and backslash/quote
            st.characters(
                blacklist_characters=['\\', '"'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # JSON number: use Hypothesis floats and ints, then convert to JSON number string
    def number_to_json(n):
        # Format floats and ints to JSON number strings
        # Use repr for floats to keep precision, but avoid inf/nan
        if isinstance(n, int):
            return str(n)
        else:
            # Clamp floats to finite values and format
            if n != n or n == float('inf') or n == float('-inf'):
                return "0"
            # Use repr to keep exponent notation if needed
            return repr(n)

    json_number = st.one_of(
        st.integers(min_value=-(10**9), max_value=10**9),
        st.floats(allow_infinity=False, allow_nan=False, width=32, min_value=-1e9, max_value=1e9),
    ).map(number_to_json)

    # Forward declare value for recursion
    # Use recursive to build arrays and objects
    json_value = st.deferred(lambda: json_value_inner)

    # JSON array: bounded length, elements are json_value
    json_array = st.lists(json_value, min_size=0, max_size=5).map(
        lambda vs: "[" + ",".join(vs) + "]"
    )

    # JSON pair: string key + colon + value
    json_pair = st.tuples(json_string, json_value).map(
        lambda kv: kv[0] + ":" + kv[1]
    )

    # JSON object: bounded number of pairs, keys unique by chance
    json_object = st.lists(json_pair, min_size=0, max_size=5).map(
        lambda pairs: "{" + ",".join(pairs) + "}"
    )

    # Compose json_value_inner with all possible JSON values
    json_value_inner = st.one_of(
        json_string,
        json_number,
        json_object,
        json_array,
        json_true,
        json_false,
        json_null,
    )

    # Draw a full JSON value and append EOF (not strictly needed for bytes)
    json_text = draw(json_value)

    # Return as bytes (UTF-8)
    return json_text.encode("utf-8")