from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # JSON strings: use Hypothesis text with safe codepoints excluding control chars and quotes/backslash
    json_string = st.text(
        alphabet=(
            # all Unicode except control chars (U+0000-U+001F), quote, backslash
            # Hypothesis text default excludes surrogates, so safe
            # We'll exclude '"' (U+0022) and '\\' (U+005C)
            # Control chars: 0x00-0x1F
            # So alphabet: all chars >= 0x20 except '"' and '\\'
            # We'll use a filter to exclude those two chars
        ),
        min_size=0,
        max_size=20,
    ).filter(lambda s: all(c not in ('"', '\\') and ord(c) >= 0x20 for c in s))
    # Escape sequences for JSON strings
    def escape_json_string(s: str) -> str:
        # Escape backslash and quote and control chars as per JSON
        def esc_char(c):
            if c == '"':
                return '\\"'
            if c == '\\':
                return '\\\\'
            if c == '\b':
                return '\\b'
            if c == '\f':
                return '\\f'
            if c == '\n':
                return '\\n'
            if c == '\r':
                return '\\r'
            if c == '\t':
                return '\\t'
            if ord(c) < 0x20:
                return '\\u%04x' % ord(c)
            return c
        return '"' + ''.join(esc_char(c) for c in s) + '"'

    json_string_escaped = json_string.map(escape_json_string)

    # Forward declaration for recursive structures
    # We'll define value recursively

    # Use st.recursive to build nested objects and arrays
    # Base: primitives
    base = st.one_of(
        json_string_escaped,
        json_number,
        json_true,
        json_false,
        json_null,
    )

    # Pair: STRING ':' value
    # STRING is json_string_escaped, but without quotes for key? No, keys are strings with quotes.
    # So keys are json_string_escaped
    # We'll generate pairs as: key + ':' + value

    def pair_strategy(value_strat):
        return st.tuples(json_string_escaped, value_strat).map(
            lambda kv: f"{kv[0]}:{kv[1]}"
        )

    # Object: '{' pair (',' pair)* '}' or '{}'
    def obj_strategy(value_strat):
        # max 3 pairs to keep size bounded
        pairs = st.lists(pair_strategy(value_strat), max_size=3)
        return pairs.map(
            lambda ps: "{" + ",".join(ps) + "}" if ps else "{}"
        )

    # Array: '[' value (',' value)* ']' or '[]'
    def arr_strategy(value_strat):
        values = st.lists(value_strat, max_size=3)
        return values.map(
            lambda vs: "[" + ",".join(vs) + "]" if vs else "[]"
        )

    # Recursive value strategy
    value = st.recursive(
        base,
        lambda children: st.one_of(
            obj_strategy(children),
            arr_strategy(children),
        ),
        max_leaves=10,
    )

    # Compose full JSON: value + EOF (implicit)
    json_str = draw(value)
    return json_str.encode("utf-8")