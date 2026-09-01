from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string: use Hypothesis built-in text with safe codepoints and escape quotes/backslashes
    # We'll generate strings without control chars and escape quotes/backslashes manually
    def json_string():
        # safe characters: no control chars, no quotes or backslash
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # generate a string of length 0-20
        s = draw(st.text(safe_chars, max_size=20))
        # escape backslash and quote
        s_escaped = s.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{s_escaped}"'

    json_number = st.builds(
        lambda n: str(n),
        st.one_of(
            st.integers(min_value=-10**6, max_value=10**6),
            st.floats(allow_nan=False, allow_infinity=False, width=32),
        ),
    )

    # Recursive definition for JSON values
    def json_value():
        # Use recursive to build nested objects and arrays with bounded depth and size
        base = st.one_of(
            st.just(json_string()),
            json_number,
            json_true,
            json_false,
            json_null,
        )

        # Compose object and array strategies
        # Use @st.composite to build pairs and arrays with drawn values

        @st.composite
        def json_pair(draw):
            k = draw(st.text(
                st.characters(
                    blacklist_characters=['"', '\\', '\u0000', '\u001F'],
                    min_codepoint=0x20,
                    max_codepoint=0x10FFFF,
                ),
                max_size=20,
            ))
            # escape key
            k_escaped = k.replace('\\', '\\\\').replace('"', '\\"')
            key = f'"{k_escaped}"'
            val = draw(json_value())
            return f"{key}:{val}"

        @st.composite
        def json_obj(draw):
            # up to 5 pairs to keep size bounded
            pairs = draw(st.lists(json_pair(), max_size=5))
            if pairs:
                return "{" + ",".join(pairs) + "}"
            else:
                return "{}"

        @st.composite
        def json_arr(draw):
            # up to 5 elements
            elems = draw(st.lists(json_value(), max_size=5))
            if elems:
                return "[" + ",".join(elems) + "]"
            else:
                return "[]"

        # recursive strategy
        return st.recursive(
            base,
            lambda children: st.one_of(
                json_obj(),
                json_arr(),
            ),
            max_leaves=10,
        )

    val = draw(json_value())
    # val is a string representing JSON text, encode as bytes
    return val.encode("utf-8")