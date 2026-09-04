from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON values
    json_null = st.just("null")
    json_bool = st.booleans().map(lambda b: "true" if b else "false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, "g"))
    # JSON strings: use Hypothesis text with safe codepoints, escape quotes and backslashes
    def escape_json_string(s: str) -> str:
        # Escape backslash and double quote, and control chars as \uXXXX
        def esc_char(c):
            if c == '"':
                return r'\"'
            if c == '\\':
                return r'\\'
            if ord(c) < 0x20:
                return "\\u%04x" % ord(c)
            return c
        return '"' + "".join(esc_char(c) for c in s) + '"'
    json_string = st.text(
        alphabet=st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=20,
    ).map(escape_json_string)

    # Recursive strategy for JSON values with bounded depth and size
    # Use st.recursive with max_leaves to limit complexity
    base = st.one_of(json_null, json_bool, json_number, json_string)

    # Compose objects and arrays recursively
    def json_obj():
        # pair: STRING ':' value
        pair = st.tuples(json_string, generated_json_value).map(lambda p: p[0] + ":" + p[1])
        # object: '{' pair (',' pair)* '}' or '{}'
        return st.lists(pair, max_size=3).map(
            lambda pairs: "{" + ",".join(pairs) + "}" if pairs else "{}"
        )

    def json_arr():
        # array: '[' value (',' value)* ']' or '[]'
        return st.lists(generated_json_value, max_size=3).map(
            lambda values: "[" + ",".join(values) + "]" if values else "[]"
        )

    # Use st.recursive to define generated_json_value
    # We define generated_json_value here to avoid forward reference issues
    global generated_json_value
    generated_json_value = st.recursive(
        base,
        lambda children: st.one_of(json_obj(), json_arr()),
        max_leaves=10,
    )

    # Draw a JSON value and append EOF (nothing)
    val = draw(generated_json_value)
    return val.encode("utf-8")