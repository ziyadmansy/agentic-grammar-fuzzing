from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll limit length to keep size bounded
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and " \)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escapes: \", \\, \b, \f, \n, \r, \t and unicode escapes
        escapes = st.sampled_from([
            r'\"', r'\\', r'\b', r'\f', r'\n', r'\r', r'\t'
        ])
        # Unicode escape: \uXXXX with hex digits
        hex_digit = st.characters(min_codepoint=0x30, max_codepoint=0x39).filter(lambda c: c in "0123456789abcdefABCDEF")
        # We'll generate either safe chars or escapes or unicode escapes
        def json_char():
            # 70% safe char, 20% simple escape, 10% unicode escape
            return st.one_of(
                safe_char,
                escapes,
                st.builds(lambda h1,h2,h3,h4: f"\\u{h1}{h2}{h3}{h4}",
                          hex_digit, hex_digit, hex_digit, hex_digit)
            )
        # Compose string content with length 0..20
        content = st.lists(json_char(), max_size=20).map("".join)
        return content.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # NUMBER strategy: use Hypothesis built-in floats converted to JSON number strings
    # but restrict to finite numbers and reasonable ranges
    def json_number():
        # Generate numbers as strings matching the grammar
        # We'll generate int or float or exponent forms
        # Use floats but convert to JSON number strings carefully
        def float_to_json_number(f):
            # Convert float to JSON number string without trailing .0 if possible
            import math
            if math.isinf(f) or math.isnan(f):
                # fallback to 0
                return "0"
            s = repr(f)
            # repr can produce 'inf', 'nan', etc. We filtered above.
            # Remove trailing .0 if integer
            if '.' in s or 'e' in s or 'E' in s:
                return s.lower()
            else:
                return s
        # Generate floats in a bounded range to avoid huge exponents
        floats = st.floats(min_value=-1e6, max_value=1e6, allow_infinity=False, allow_nan=False)
        return floats.map(float_to_json_number)

    json_number_st = json_number()

    # Forward declaration for recursive structures
    # We'll use st.recursive to build obj and arr

    # Pair: STRING : value
    # We'll build pairs as strings: "string":value
    # We'll generate keys as strings (no duplicates enforced)
    # We'll generate values recursively

    # Define value strategy recursively
    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string_st,
        json_number_st,
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: obj and arr
    # We'll define them inside a function to use st.recursive

    def json_value():
        # Recursive strategy for value
        # Compose obj and arr later
        return st.deferred(lambda: value_strategy)

    # Pair strategy: "string":value
    # We'll generate keys as strings without escapes for simplicity (safe ASCII)
    key_char = st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc'),  # letters, digits, underscore
        min_codepoint=0x20, max_codepoint=0x7E
    )
    key_string = st.text(key_char, min_size=1, max_size=10).map(lambda s: f'"{s}"')

    @st.composite
    def pair(draw):
        k = draw(key_string)
        v = draw(json_value())
        return f"{k}:{v}"

    # Object strategy: { pair (, pair)* } or {}
    @st.composite
    def obj(draw):
        # Generate 0..5 pairs (small to keep size bounded)
        pairs = draw(st.lists(pair(), max_size=5))
        if not pairs:
            return "{}"
        return "{" + ",".join(pairs) + "}"

    # Array strategy: [ value (, value)* ] or []
    @st.composite
    def arr(draw):
        values = draw(st.lists(json_value(), max_size=5))
        if not values:
            return "[]"
        return "[" + ",".join(values) + "]"

    # Now define value_strategy recursively
    # base_values plus obj and arr
    value_strategy = st.recursive(
        base_values,
        lambda children: st.one_of(obj(), arr()),
        max_leaves=10,
    )

    # Compose final json: value + EOF (just value here)
    json_text = draw(value_strategy)
    return json_text.encode("utf-8")