from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives as strings
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: valid JSON strings with escapes
    # We'll generate Python strings and then encode them as JSON strings
    # Use st.text with safe codepoints excluding control chars and quotes/backslash
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars, " and \)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Generate a string of length 0-20
        s = st.text(safe_chars, min_size=0, max_size=20)

        # Escape special characters per JSON spec
        def escape_json_str(s):
            # Escape backslash and quote
            s = s.replace('\\', '\\\\').replace('"', '\\"')
            # Escape control chars (U+0000 to U+001F) as \uXXXX
            def esc_char(c):
                if ord(c) < 0x20:
                    return '\\u%04x' % ord(c)
                return c
            s = ''.join(esc_char(c) for c in s)
            return f'"{s}"'

        return s.map(escape_json_str)

    json_string_strat = json_string()

    # NUMBER strategy: generate JSON numbers as strings
    # Use hypothesis floats converted to JSON number strings, but avoid NaN/inf
    def json_number():
        # Generate floats in a reasonable range, exclude NaN/inf
        f = st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e10,
            max_value=1e10,
        )
        # Convert float to JSON number string, using repr to avoid trailing zeros
        def float_to_json_num(x):
            # Use repr to get shortest representation
            s = repr(x)
            # repr may produce 'inf', 'nan' but filtered above
            # Also, repr may produce '1e-07' which is valid JSON number
            return s
        return f.map(float_to_json_num)

    json_number_strat = json_number()

    # Recursive JSON value strategy
    # We'll define a recursive strategy for value:
    # value = string | number | obj | arr | true | false | null

    # Forward declaration for value
    # Use st.deferred to allow recursion
    @st.composite
    def json_value(draw):
        # Compose base values
        base = st.one_of(
            json_string_strat,
            json_number_strat,
            json_true,
            json_false,
            json_null,
        )

        # Recursive container strategies
        # obj: '{' pair (',' pair)* '}' or '{}'
        # pair: STRING ':' value
        # arr: '[' value (',' value)* ']' or '[]'

        # To avoid infinite recursion, limit max depth
        # We'll pass depth parameter internally
        def json_obj(depth):
            if depth <= 0:
                # Empty object only
                return st.just("{}")
            # pair: STRING ':' value
            def pair():
                k = json_string_strat
                v = json_value_with_depth(depth - 1)
                return st.tuples(k, v).map(lambda kv: f"{kv[0]}:{kv[1]}")

            pairs = st.lists(pair(), max_size=5)
            return pairs.map(
                lambda ps: "{" + ",".join(ps) + "}" if ps else "{}"
            )

        def json_arr(depth):
            if depth <= 0:
                return st.just("[]")
            vals = st.lists(json_value_with_depth(depth - 1), max_size=5)
            return vals.map(
                lambda vs: "[" + ",".join(vs) + "]" if vs else "[]"
            )

        # Compose full value strategy with recursion
        def json_value_with_depth(depth):
            if depth <= 0:
                return base
            return st.one_of(
                base,
                json_obj(depth),
                json_arr(depth),
            )

        # Start with max depth 3
        return draw(json_value_with_depth(3))

    # Compose full JSON text: value EOF
    json_text = json_value()

    # Draw the JSON string and encode as bytes
    s = draw(json_text)
    return s.encode("utf-8")