from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: simple ASCII strings with escapes
    # Use a small subset of safe characters plus escapes
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\b', r'\f', r'\n', r'\r', r'\t',
        ])
        # Unicode escape \uXXXX with hex digits
        hex_digit = st.sampled_from('0123456789abcdefABCDEF')
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))

        # Either safe char or escape sequence
        char_or_escape = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Build string content with length 0..20
        content = st.lists(char_or_escape, max_size=20).map(''.join)
        return content.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # NUMBER strategy: use Hypothesis floats and ints formatted as JSON numbers
    # We'll generate numbers as strings to preserve JSON format
    def json_number():
        # Generate numbers as strings matching the grammar
        # Use floats and ints, including negative and exponentials
        def number_to_json(n):
            # Format int or float to JSON number string
            if isinstance(n, int):
                return str(n)
            else:
                # Format float with repr to preserve exponentials
                s = repr(n)
                # repr can produce inf/nan, avoid those
                if s in ('inf', '-inf', 'nan', '-nan'):
                    return "0"
                return s
        # Generate int or float in a reasonable range
        # Use floats with limited magnitude to avoid huge exponents
        num = st.one_of(
            st.integers(min_value=-10**6, max_value=10**6),
            st.floats(min_value=-1e6, max_value=1e6, allow_infinity=False, allow_nan=False)
        )
        return num.map(number_to_json)

    json_number_st = json_number()

    # Forward declare value strategy to allow recursion
    # We'll use st.recursive to build nested objects and arrays
    # Limit max depth and size to keep examples bounded

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string_st,
        json_number_st,
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: objects and arrays
    # Use @st.composite to build pairs and objects

    @st.composite
    def json_pair(draw):
        key = draw(json_string_st)
        val = draw(value_st)
        return f"{key}:{val}"

    @st.composite
    def json_object(draw):
        # Either empty or non-empty object
        # Limit number of pairs to max 5
        pairs = draw(st.lists(json_pair(), max_size=5))
        if pairs:
            return "{" + ",".join(pairs) + "}"
        else:
            return "{}"

    @st.composite
    def json_array(draw):
        # Either empty or non-empty array
        # Limit number of elements to max 5
        elements = draw(st.lists(value_st, max_size=5))
        if elements:
            return "[" + ",".join(elements) + "]"
        else:
            return "[]"

    # Compose value strategy recursively
    # Use st.recursive with base_values and containers

    def containers(children):
        return st.one_of(
            json_object(),
            json_array(),
        )

    value_st = st.recursive(base_values, containers, max_leaves=10)

    # Draw a full JSON value and append EOF (nothing)
    json_text = draw(value_st)

    return json_text.encode("utf-8")