from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives as strings
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string: use Hypothesis text with safe codepoints, escape quotes and backslashes
    def json_string():
        # Use safe unicode characters excluding control chars and quotes/backslash
        # We'll escape quotes and backslash manually
        def escape_json_str(s: str) -> str:
            # Escape backslash and quote
            s = s.replace('\\', '\\\\').replace('"', '\\"')
            # Escape control chars (0x00-0x1F) as \uXXXX
            def esc_char(c):
                if ord(c) < 0x20:
                    return '\\u%04x' % ord(c)
                return c
            s = ''.join(esc_char(c) for c in s)
            return s

        raw = draw(st.text(min_size=0, max_size=20))
        escaped = escape_json_str(raw)
        return f'"{escaped}"'

    json_number = st.one_of(
        st.integers(min_value=-10**6, max_value=10**6).map(str),
        st.floats(allow_infinity=False, allow_nan=False, width=32).map(lambda f: format(f, 'g'))
    )

    # Recursive JSON values
    # We'll define a recursive strategy for JSON values as strings

    # Forward declaration for recursive
    json_value = st.deferred()

    json_array = st.lists(json_value, min_size=0, max_size=5).map(
        lambda vs: "[" + ",".join(vs) + "]"
    )

    json_pair = st.tuples(json_string(), json_value).map(
        lambda kv: f"{kv[0]}:{kv[1]}"
    )

    json_object = st.lists(json_pair, min_size=0, max_size=5).map(
        lambda pairs: "{" + ",".join(pairs) + "}"
    )

    json_value_strategy = st.one_of(
        json_string(),
        json_number,
        json_object,
        json_array,
        json_true,
        json_false,
        json_null,
    )

    # Assign to deferred
    json_value = json_value_strategy

    # Draw the top-level JSON value
    result = draw(json_value)

    return result.encode("utf-8")