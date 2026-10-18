from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe code points
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and " \)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape sequences
        def unicode_escape():
            hex_digit = st.characters("0123456789abcdefABCDEF")
            return st.tuples(hex_digit, hex_digit, hex_digit, hex_digit).map(
                lambda hs: "\\u" + "".join(hs)
            )
        escape_seq = st.one_of(escapes, unicode_escape())
        # Mix safe chars and escapes
        chunk = st.one_of(safe_char.map(lambda c: c), escape_seq)
        # Build string with length limit to keep size bounded
        content = st.lists(chunk, max_size=20).map("".join)
        return content.map(lambda s: f'"{s}"')

    # NUMBER strategy: produce valid JSON numbers
    def json_number():
        # Use Hypothesis floats converted to JSON number strings, but restrict to finite numbers
        # To keep near-valid, also allow integers and floats with exponent
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        frac_part = st.one_of(st.just(""), st.floats(min_value=0, max_value=1).map(lambda f: f"{f}".partition(".")[2]))
        # We'll build numbers manually to avoid invalid float formatting
        def build_number():
            sign = st.one_of(st.just(""), st.just("-"))
            intp = int_part
            frac = st.one_of(st.just(""), st.text(min_size=1, max_size=5, alphabet="0123456789"))
            exp = st.one_of(
                st.just(""),
                st.tuples(
                    st.sampled_from(["e", "E"]),
                    st.one_of(st.just("+"), st.just("-"), st.just("")),
                    st.integers(min_value=0, max_value=99).map(str)
                ).map(lambda t: t[0] + t[1] + t[2])
            )
            return st.tuples(sign, intp, frac, exp).map(lambda t: t[0] + t[1] + (("." + t[2]) if t[2] else "") + t[3])
        return build_number()

    # Recursive JSON value strategy
    # Use st.recursive to keep size bounded
    base = st.one_of(
        json_string(),
        json_number(),
        json_true,
        json_false,
        json_null,
    )

    # Forward declarations for obj and arr to be used recursively
    # obj: '{' pair (',' pair)* '}' | '{}'
    # pair: STRING ':' value
    # arr: '[' value (',' value)* ']' | '[]'

    # We'll define value recursively below

    # Define pair strategy
    @st.composite
    def pair(draw):
        key = draw(json_string())
        val = draw(value)
        return f"{key}:{val}"

    # Define obj strategy
    @st.composite
    def obj(draw):
        # Empty or with pairs
        pairs = draw(st.lists(pair(), max_size=3))
        if not pairs:
            return "{}"
        return "{" + ",".join(pairs) + "}"

    # Define arr strategy
    @st.composite
    def arr(draw):
        vals = draw(st.lists(value, max_size=3))
        if not vals:
            return "[]"
        return "[" + ",".join(vals) + "]"

    # Now define value recursively
    # We use st.recursive with base and extend with obj and arr
    value = st.recursive(
        base,
        lambda children: st.one_of(
            obj(),
            arr(),
        ),
        max_leaves=5,
    )

    # Draw a full JSON value and append EOF (implicit)
    result = draw(value)
    return result.encode("utf-8")