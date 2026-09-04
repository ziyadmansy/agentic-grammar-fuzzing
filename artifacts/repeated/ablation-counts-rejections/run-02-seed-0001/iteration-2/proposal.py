from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_nan=False, allow_infinity=False).map(lambda n: format(n, '.15g'))
    # STRING: roughly safe JSON strings with escapes
    # We'll generate unicode strings excluding control chars and quotes/backslash,
    # then escape quotes and backslashes manually.
    def escape_json_string(s: str) -> str:
        # Escape backslash and quote, and control chars as \uXXXX
        def esc_char(c):
            if c == '"':
                return r'\"'
            elif c == '\\':
                return r'\\'
            elif ord(c) < 0x20:
                return '\\u%04x' % ord(c)
            else:
                return c
        return '"' + ''.join(esc_char(c) for c in s) + '"'
    json_string_raw = st.text(
        alphabet=st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=20,
    )
    json_string = json_string_raw.map(escape_json_string)

    # Recursive JSON values: obj and arr
    # We'll define a recursive strategy for value first
    # Use st.recursive with base cases: string, number, true, false, null

    base = st.one_of(json_string, json_number, json_true, json_false, json_null)

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
        n = draw(st.integers(min_value=0, max_value=5))
        if n == 0:
            return "{}"
        pairs = [draw(pair) for _ in range(n)]
        return "{" + ",".join(pairs) + "}"

    # Array: '[' value (',' value)* ']' or '[]'
    @st.composite
    def arr(draw):
        n = draw(st.integers(min_value=0, max_value=5))
        if n == 0:
            return "[]"
        values = [draw(value) for _ in range(n)]
        return "[" + ",".join(values) + "]"

    # Now define value recursively
    # We need to define value as a strategy that can refer to obj and arr,
    # but obj and arr refer to value, so we use st.recursive

    # We'll define a helper function to build value recursively
    def value_strategy():
        return st.recursive(
            base,
            lambda children: st.one_of(
                obj(),
                arr(),
            ),
            max_leaves=10,
        )

    value = value_strategy()

    # Draw a full json value and append EOF (nothing)
    result = draw(value)
    return result.encode("utf-8")