from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode them as JSON strings.
    # To keep it simple and valid, use st.text with safe chars and add escapes.
    # We'll use a small helper to produce JSON string literals.

    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        safe_chars = (
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # To include escapes, we can mix safe chars and some escapes
        # We'll generate a list of chars or escapes, then join.
        # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\b', r'\f', r'\n', r'\r', r'\t',
            # Unicode escapes: \uXXXX with hex digits
            lambda: r'\u' + ''.join(draw(st.sampled_from('0123456789abcdefABCDEF')) for _ in range(4))
        ])

        # Compose a list of either safe chars or escapes
        # To keep it simple, generate a list of length 0..20
        def char_or_escape():
            # 80% safe char, 20% escape
            return st.one_of(
                safe_chars,
                escapes.map(lambda e: e() if callable(e) else e)
            )

        # Generate list of chars/escapes
        parts = draw(st.lists(char_or_escape(), max_size=20))
        s = ''.join(parts)
        # Wrap in quotes
        return f'"{s}"'

    json_string_strategy = st.builds(json_string)

    # NUMBER strategy: use Hypothesis floats and ints, then format as JSON numbers
    # We'll generate strings that match the NUMBER grammar
    def json_number():
        # Generate a number string matching the grammar
        # Use floats and ints, then format
        # Limit exponent range to keep string short
        sign = draw(st.sampled_from(['', '-']))
        int_part = draw(st.one_of(st.just('0'), st.integers(min_value=1, max_value=10**6).map(str)))
        frac_part = draw(st.one_of(st.just(''), st.floats(min_value=0, max_value=1).map(lambda f: f"{f:.10f}".lstrip('0'))))
        # frac_part might be like '.1234567890' or ''
        if frac_part and not frac_part.startswith('.'):
            frac_part = '.' + frac_part
        exp_part = draw(st.one_of(st.just(''), st.integers(min_value=-10, max_value=10).map(lambda e: f"E{e}" if e >= 0 else f"E{e}")))
        # Compose number string
        num_str = f"{sign}{int_part}{frac_part}{exp_part}"
        # Validate by parsing float (to avoid invalid strings)
        try:
            float(num_str)
        except Exception:
            # fallback to int_part only
            num_str = f"{sign}{int_part}"
        return num_str

    json_number_strategy = st.builds(json_number)

    # Forward declaration for recursive value
    # We'll use st.recursive to build obj and arr

    # STRING and NUMBER are leaves
    leaf_values = st.one_of(
        json_string_strategy,
        json_number_strategy,
        json_null,
        json_true,
        json_false,
    )

    # obj: '{' pair (',' pair)* '}' | '{}'
    # pair: STRING ':' value
    # arr: '[' value (',' value)* ']' | '[]'

    # We define value recursively
    # We'll define pair and then obj and arr

    # To avoid infinite recursion, limit max depth and max size

    max_depth = 4
    max_pairs = 5
    max_elements = 5

    def json_value():
        # Recursive strategy for value
        # Use st.deferred to allow recursion
        return st.deferred(lambda: value_strategy)

    # pair: STRING ':' value
    @st.composite
    def json_pair(draw):
        key = draw(json_string_strategy)
        val = draw(json_value())
        return f"{key}:{val}"

    # obj: '{' pair (',' pair)* '}' | '{}'
    @st.composite
    def json_obj(draw):
        # Decide empty or not
        if draw(st.booleans()):
            return "{}"
        else:
            n = draw(st.integers(min_value=1, max_value=max_pairs))
            pairs = [draw(json_pair()) for _ in range(n)]
            return "{" + ",".join(pairs) + "}"

    # arr: '[' value (',' value)* ']' | '[]'
    @st.composite
    def json_arr(draw):
        if draw(st.booleans()):
            return "[]"
        else:
            n = draw(st.integers(min_value=1, max_value=max_elements))
            elements = [draw(json_value()) for _ in range(n)]
            return "[" + ",".join(elements) + "]"

    # Compose value_strategy with recursion
    value_strategy = st.recursive(
        leaf_values,
        lambda children: st.one_of(
            json_obj(),
            json_arr(),
        ),
        max_leaves=100,
    )

    # Compose full json: value EOF
    json_text = draw(value_strategy)
    # Return bytes
    return json_text.encode("utf-8")