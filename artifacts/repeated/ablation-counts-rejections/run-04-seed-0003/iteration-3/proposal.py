from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: use Hypothesis text with safe codepoints, escape as needed
    # We'll generate strings without control chars and escape quotes and backslashes
    def json_string():
        # Safe codepoints: exclude control chars and backslash and quote
        safe_chars = st.characters(
            blacklist_characters=['\\', '"'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Generate strings up to length 20 for bounded size
        s = st.text(safe_chars, max_size=20)

        # Escape backslash and quote in the string
        def escape_json_string(text):
            # Escape backslash and quote
            text = text.replace('\\', '\\\\').replace('"', '\\"')
            # Also escape control chars if any (shouldn't be present)
            # but just in case, replace control chars with \uXXXX
            def esc_char(c):
                if ord(c) < 0x20:
                    return f"\\u{ord(c):04x}"
                return c
            return ''.join(esc_char(c) for c in text)

        return s.map(lambda t: '"' + escape_json_string(t) + '"')

    json_number = st.one_of(
        # integers and floats with optional exponent, bounded size
        st.integers(min_value=-10**6, max_value=10**6).map(str),
        st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ).map(lambda f: format(f, '.6g')),
    )

    # Recursive JSON values: string, number, obj, arr, true, false, null
    # Use st.recursive with max_depth to avoid max recursion depth exceeded
    base = st.one_of(
        json_string(),
        json_number,
        json_true,
        json_false,
        json_null,
    )

    # Define obj and arr recursively
    def json_obj():
        # pair: STRING ':' value
        pair = st.tuples(json_string(), json_value).map(lambda p: p[0] + ":" + p[1])
        # object: '{' pair (',' pair)* '}' or '{}'
        # limit number of pairs to max 3 for bounded size
        pairs = st.lists(pair, max_size=3)
        return pairs.map(lambda ps: "{" + ",".join(ps) + "}" if ps else "{}")

    def json_arr():
        # array: '[' value (',' value)* ']' or '[]'
        # limit number of elements to max 3 for bounded size
        elems = st.lists(json_value, max_size=3)
        return elems.map(lambda es: "[" + ",".join(es) + "]" if es else "[]")

    # We need to define json_value here to use in obj and arr
    # Use st.recursive to tie the knot
    json_value = st.deferred()

    json_value_strategy = st.recursive(
        base,
        lambda children: st.one_of(
            json_obj(),
            json_arr(),
        ),
        max_leaves=10,
    )

    # Assign the deferred strategy
    json_value.define(json_value_strategy)

    # Draw the final JSON string and encode as bytes
    s = draw(json_value)
    return s.encode("utf-8")