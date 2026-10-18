from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode them as JSON strings.
    # To keep it simple and valid, use st.text with safe characters and escape quotes/backslashes.
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        safe_chars = (
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # Compose a string with safe chars and some escapes
        base_str = st.text(safe_chars, min_size=0, max_size=20)

        # We will escape quotes and backslashes manually
        def escape_json_str(s: str) -> str:
            # Escape backslash and quote
            s = s.replace('\\', '\\\\').replace('"', '\\"')
            # Also escape control chars (0x00-0x1F) as \u00XX
            def esc_char(c):
                if ord(c) < 0x20:
                    return '\\u%04x' % ord(c)
                return c
            s = ''.join(esc_char(c) for c in s)
            return f'"{s}"'

        return base_str.map(escape_json_str)

    json_string_st = json_string()

    # NUMBER strategy: produce valid JSON numbers as strings
    # Use Hypothesis floats converted to JSON number strings, but avoid NaN/inf
    def json_number():
        # Generate floats with limited range and precision to keep output small
        # Also generate integers as strings
        int_str = st.integers(min_value=-10**6, max_value=10**6).map(str)
        float_str = st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ).map(lambda f: format(f, '.6g'))
        return st.one_of(int_str, float_str)

    json_number_st = json_number()

    # Recursive JSON value strategy
    # We'll use st.recursive to build arrays and objects with bounded depth and size
    # Base cases: string, number, true, false, null
    base = st.one_of(
        json_string_st,
        json_number_st,
        json_true,
        json_false,
        json_null,
    )

    # Compose pair: STRING ':' value
    @st.composite
    def pair(draw):
        key = draw(json_string_st)
        val = draw(value)
        return f"{key}:{val}"

    # We need to define value before pair, so use a trick with a placeholder
    # We'll define value as a recursive strategy after pair is defined

    # Placeholder for value to allow recursion
    value = st.deferred(lambda: value_inner)

    # Array: '[' value (',' value)* ']' or '[]'
    @st.composite
    def array(draw):
        # Generate list of values (0 to 5 elements)
        elements = draw(st.lists(value, max_size=5))
        if not elements:
            return "[]"
        return "[" + ",".join(elements) + "]"

    # Object: '{' pair (',' pair)* '}' or '{}'
    @st.composite
    def obj(draw):
        pairs = draw(st.lists(pair, max_size=5))
        if not pairs:
            return "{}"
        return "{" + ",".join(pairs) + "}"

    # Now define value_inner as recursive
    value_inner = st.recursive(
        base,
        lambda children: st.one_of(
            obj(),
            array(),
        ),
        max_leaves=10,
    )

    # Compose full JSON document: value + EOF (implicit)
    json_text = draw(value)

    # Return as bytes
    return json_text.encode("utf-8")