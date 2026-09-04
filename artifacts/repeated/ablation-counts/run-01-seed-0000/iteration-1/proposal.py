from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly matching grammar, with safe codepoints and escapes
    # We'll generate Python strings and then JSON-encode them with repr-like escapes.
    # But to keep it simple, generate strings with safe chars and some escapes.
    # We'll generate strings with safe Unicode codepoints excluding control chars and quotes/backslash.
    # Then encode with JSON-style escapes.
    def json_string():
        # safe chars excluding " and \ and control chars
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # To include some escapes, we can occasionally insert an escape sequence
        # but to keep it simple, just generate safe strings and then escape quotes and backslashes.
        s = draw(st.text(safe_chars, min_size=0, max_size=20))
        # Escape backslash and quote
        s_escaped = s.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{s_escaped}"'

    json_string_st = st.deferred(lambda: st.builds(lambda s: s, st.just(json_string())))

    # NUMBER: generate numbers as strings matching grammar
    def json_number():
        # Generate floats and ints, then convert to string matching grammar
        # Use Hypothesis floats and ints, then format accordingly
        # To keep it simple, generate int or float strings with optional exponent
        # We'll generate a float or int and format it as JSON number string
        # Use st.floats with finite=True, allow_infinity=False, allow_nan=False
        # Limit magnitude to keep strings short
        is_int = draw(st.booleans())
        if is_int:
            i = draw(st.integers(min_value=-10**6, max_value=10**6))
            return str(i)
        else:
            f = draw(st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False))
            # Format float with minimal digits, no trailing zeros
            s = format(f, '.10g')
            # Ensure it matches JSON number grammar: no leading +, no trailing dot
            # If s contains 'e' or 'E', keep as is
            # If s ends with '.', remove it
            if s.endswith('.'):
                s = s[:-1]
            return s

    json_number_st = st.deferred(lambda: st.builds(lambda s: s, st.just(json_number())))

    # Recursive strategy for value
    # We'll use st.recursive to build nested objects and arrays

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        st.builds(lambda s: s, st.just(json_string())),
        st.builds(lambda s: s, st.just(json_number())),
        json_true,
        json_false,
        json_null,
    )

    # Forward declare value strategy to use in recursive
    def value_strategy():
        return st.deferred(lambda: value_st)

    # pair: STRING ':' value
    @st.composite
    def pair(draw):
        key = draw(json_string_st)
        val = draw(value_strategy())
        return f"{key}:{val}"

    # obj: '{' pair (',' pair)* '}' | '{}'
    @st.composite
    def obj(draw):
        # Generate 0 to 5 pairs
        pairs = draw(st.lists(pair(), max_size=5))
        if not pairs:
            return "{}"
        return "{" + ",".join(pairs) + "}"

    # arr: '[' value (',' value)* ']' | '[]'
    @st.composite
    def arr(draw):
        values = draw(st.lists(value_strategy(), max_size=5))
        if not values:
            return "[]"
        return "[" + ",".join(values) + "]"

    # Now define value_st recursively
    value_st = st.recursive(
        base_values,
        lambda children: st.one_of(
            obj(),
            arr(),
        ),
        max_leaves=10,
    )

    # Compose full json: value EOF
    json_text = draw(value_st)
    return json_text.encode("utf-8")