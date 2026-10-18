from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: simple ASCII strings with escapes
    # We'll generate strings without control chars and with some escapes
    def json_string():
        # safe codepoints excluding control chars and quotes/backslash
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # small strings for bounded size
        base_str = st.text(safe_chars, max_size=10)

        # We add some escapes occasionally
        def escape_inserter(s):
            # randomly insert some escapes
            import random
            escapes = ['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t']
            s_list = list(s)
            for i in range(len(s_list)):
                if random.random() < 0.1:
                    s_list[i] = random.choice(escapes)
            return ''.join(s_list)

        # We can't use random inside strategies, so just generate strings with escapes manually
        # Instead, generate strings with some escapes by mixing safe chars and escapes
        esc_char = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        part = st.one_of(
            st.characters(
                blacklist_characters=['"', '\\', '\u0000', '\u001F'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            ).map(lambda c: c),
            esc_char,
        )
        # build small string of length up to 10
        s = st.lists(part, max_size=10).map(''.join)
        # wrap in quotes
        return s.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # NUMBER strategy: integers and floats with optional exponent
    json_number = st.one_of(
        st.integers(min_value=-1_000_000, max_value=1_000_000).map(str),
        st.floats(allow_infinity=False, allow_nan=False, width=32).map(lambda f: format(f, 'g')),
    )

    # Recursive value strategy
    # We'll define a recursive strategy for values, bounded in depth and size

    # Forward declaration for value
    # We use st.deferred to allow recursion
    def json_value():
        return st.deferred(lambda: value_strategy)

    # Pair: STRING ':' value
    @st.composite
    def json_pair(draw):
        k = draw(json_string_st)
        v = draw(json_value())
        return f"{k}:{v}"

    # Object: '{' pair (',' pair)* '}' or '{}'
    @st.composite
    def json_object(draw):
        # up to 3 pairs to keep size bounded
        pairs = draw(st.lists(json_pair(), max_size=3))
        if pairs:
            return "{" + ",".join(pairs) + "}"
        else:
            return "{}"

    # Array: '[' value (',' value)* ']' or '[]'
    @st.composite
    def json_array(draw):
        vals = draw(st.lists(json_value(), max_size=3))
        if vals:
            return "[" + ",".join(vals) + "]"
        else:
            return "[]"

    # Compose value strategy with recursion bounded
    value_strategy = st.recursive(
        st.one_of(
            json_string_st,
            json_number,
            json_null,
            json_true,
            json_false,
        ),
        lambda children: st.one_of(
            json_object(),
            json_array(),
        ),
        max_leaves=10,
    )

    # Draw the top-level JSON value and append EOF (nothing)
    result = draw(value_strategy)
    return result.encode("utf-8")