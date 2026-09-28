from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string with safe codepoints and escapes
    # SAFECODEPOINT ~["\\\u0000-\u001F], so exclude control chars and backslash and quote
    # We'll allow common escapes as well
    def json_string():
        # Characters allowed inside strings (excluding control chars, backslash, quote)
        safe_chars = st.characters(
            blacklist_characters=['\\', '"'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t',
        ])
        # Unicode escape: \u followed by 4 hex digits
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))

        # Compose string content: mix of safe chars and escapes
        # To keep it simple, generate a list of elements each either a safe char or an escape
        content_element = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Generate between 0 and 20 elements to keep size bounded
        content = st.lists(content_element, max_size=20).map(''.join)
        return content.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # JSON number: use Hypothesis floats and ints, then format to JSON number string
    def json_number():
        # Generate numbers as strings matching the grammar
        # We'll generate floats and ints, then format accordingly
        # To keep it simple, generate floats with limited exponent range
        def format_number(n):
            # Format float or int to JSON number string
            # Use repr to get a compact representation
            s = repr(n)
            # Ensure exponent uses E or e with optional +/-
            # repr already does this correctly
            return s

        # Generate floats in a reasonable range to avoid huge exponents
        return st.one_of(
            st.integers(min_value=-10**6, max_value=10**6).map(format_number),
            st.floats(
                allow_infinity=False,
                allow_nan=False,
                width=32,
                min_value=-1e6,
                max_value=1e6,
            ).map(format_number),
        )

    json_number_st = json_number()

    # Recursive JSON value strategy
    # Use st.recursive to build nested objects and arrays, bounded to avoid explosion
    base = st.one_of(
        json_string_st,
        json_number_st,
        json_null,
        json_true,
        json_false,
    )

    # Pair: STRING ':' value
    @st.composite
    def pair(draw):
        k = draw(json_string_st)
        v = draw(value)
        return f"{k}:{v}"

    # Forward declaration for recursive use
    # We'll define value after obj and arr to allow recursion
    # Use a mutable container to hold the strategy
    value = st.deferred(lambda: value_strategy)

    # Object: '{' pair (',' pair)* '}' or '{}'
    @st.composite
    def obj(draw):
        # Generate 0 to 5 pairs to keep size bounded
        pairs = draw(st.lists(pair(), max_size=5))
        if not pairs:
            return "{}"
        return "{" + ",".join(pairs) + "}"

    # Array: '[' value (',' value)* ']' or '[]'
    @st.composite
    def arr(draw):
        # Generate 0 to 5 values
        values = draw(st.lists(value, max_size=5))
        if not values:
            return "[]"
        return "[" + ",".join(values) + "]"

    # Now define value_strategy using recursive
    value_strategy = st.recursive(
        base,
        lambda children: st.one_of(
            obj(),
            arr(),
        ),
        max_leaves=10,
    )

    # Compose full JSON: value + EOF (implicit)
    json_text = draw(value_strategy)
    return json_text.encode("utf-8")