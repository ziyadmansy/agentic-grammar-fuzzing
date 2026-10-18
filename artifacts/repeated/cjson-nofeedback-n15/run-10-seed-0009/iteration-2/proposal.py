from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: roughly valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings then encode as JSON strings with quotes and escapes.
    # To keep it simple, use Hypothesis's built-in json string strategy and tweak it.
    # But since we can't import hypothesis-json, we build a simple string strategy.

    # Characters allowed in JSON strings (excluding control chars and quotes/backslash)
    safe_char = st.characters(
        blacklist_characters=['"', '\\'],
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    )
    # Escape sequences: \", \\, \b, \f, \n, \r, \t, \uXXXX
    # We'll randomly insert escapes in strings.
    def json_string_chars():
        # Either a safe char or an escape sequence
        esc_simple = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        esc_unicode = st.builds(
            lambda h1,h2,h3,h4: '\\u' + h1 + h2 + h3 + h4,
            st.sampled_from('0123456789abcdef'),
            st.sampled_from('0123456789abcdef'),
            st.sampled_from('0123456789abcdef'),
            st.sampled_from('0123456789abcdef'),
        )
        return st.one_of(safe_char.map(lambda c: c), esc_simple, esc_unicode)

    # Compose a string of length 0..20
    json_string_inner = st.lists(json_string_chars(), max_size=20).map("".join)
    json_string = json_string_inner.map(lambda s: '"' + s + '"')

    # NUMBER strategy: use Hypothesis floats and ints, then convert to JSON number strings
    # We'll generate numbers as strings matching the grammar
    def number_to_json(n):
        # Format number as JSON number string
        # Use repr for floats, str for ints, but ensure no trailing .0 for ints
        if isinstance(n, int):
            return str(n)
        else:
            # Use repr, but avoid scientific notation for small numbers
            # We'll allow scientific notation as it's valid JSON
            return repr(n)

    json_number = st.one_of(
        st.integers(min_value=-(10**6), max_value=10**6),
        st.floats(allow_nan=False, allow_infinity=False, width=32, min_value=-1e6, max_value=1e6),
    ).map(number_to_json)

    # Forward declaration for recursive structures
    # We'll build value strategy recursively

    # Use st.recursive to build nested objects and arrays
    base = st.one_of(json_string, json_number, json_null, json_true, json_false)

    # Pair: STRING ':' value
    @st.composite
    def pair(draw, value_strat):
        k = draw(json_string)
        v = draw(value_strat)
        return k + ":" + v

    # Object: '{' pair (',' pair)* '}' or '{}'
    def obj_strategy(value_strat):
        # 0 to 5 pairs
        pairs = st.lists(pair(value_strat), max_size=5)
        return pairs.map(lambda ps: "{" + ",".join(ps) + "}" if ps else "{}")

    # Array: '[' value (',' value)* ']' or '[]'
    def arr_strategy(value_strat):
        values = st.lists(value_strat, max_size=5)
        return values.map(lambda vs: "[" + ",".join(vs) + "]" if vs else "[]")

    # Recursive value strategy
    value = st.recursive(
        base,
        lambda children: st.one_of(
            obj_strategy(children),
            arr_strategy(children),
        ),
        max_leaves=10,
    )

    # Compose full JSON: value + EOF (just value here)
    json_str = draw(value)
    return json_str.encode("utf-8")