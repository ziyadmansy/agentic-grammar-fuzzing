from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string with safe codepoints and escapes
    # SAFECODEPOINT ~["\\\u0000-\u001F], so exclude control chars and backslash and quote
    # We'll allow some escapes to preserve near-valid cases
    # Use a small max_size to keep sizes bounded
    json_string = st.text(
        alphabet=(
            # safe codepoints: all printable except backslash and quote and control chars
            # We'll use ASCII printable except backslash and quote and control chars
            # ASCII 0x20-0x21, 0x23-0x5B, 0x5D-0x7E
            ''.join(chr(c) for c in range(0x20, 0x7F) if c not in (0x22, 0x5C))
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s + '"')

    # JSON number: use Hypothesis floats converted to JSON number strings
    # We'll generate numbers as strings to preserve formatting
    def number_str():
        # Generate a float or int string with optional exponent
        # Limit size to keep bounded
        # Use floats in range to avoid huge exponents
        return st.one_of(
            st.integers(min_value=-10**6, max_value=10**6).map(str),
            st.floats(min_value=-1e6, max_value=1e6, allow_infinity=False, allow_nan=False).map(
                lambda f: format(f, '.6g')
            ),
        )
    json_number = number_str()

    # Recursive JSON value
    # Use st.recursive to build nested objects and arrays
    base = st.one_of(json_string, json_number, json_null, json_true, json_false)

    # Pair: STRING ':' value
    @st.composite
    def pair(draw):
        k = draw(json_string)
        v = draw(value)
        return f"{k}:{v}"

    # Object: '{' pair (',' pair)* '}' or '{}'
    @st.composite
    def obj(draw):
        # limit number of pairs to keep size bounded
        pairs = draw(st.lists(pair(), max_size=4))
        if pairs:
            return "{" + ",".join(pairs) + "}"
        else:
            return "{}"

    # Array: '[' value (',' value)* ']' or '[]'
    @st.composite
    def arr(draw):
        values = draw(st.lists(value, max_size=4))
        if values:
            return "[" + ",".join(values) + "]"
        else:
            return "[]"

    # Now define value as recursive
    value = st.recursive(
        base,
        lambda children: st.one_of(obj(), arr()),
        max_leaves=10,
    )

    # Draw the final JSON text and encode as bytes
    json_text = draw(value)
    return json_text.encode("utf-8")