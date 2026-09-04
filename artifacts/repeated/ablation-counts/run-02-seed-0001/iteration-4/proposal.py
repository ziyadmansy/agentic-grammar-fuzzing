from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON strings: use ASCII printable except control chars and backslash/quote
    # to approximate SAFECODEPOINT, plus escapes
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars, backslash, quote)
        safe_chars = st.characters(
            blacklist_characters=['\\', '"'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Build string content with safe chars and some escapes
        # We include escapes by mixing safe chars and escaped sequences
        # Escapes: \" \\ \/ \b \f \n \r \t and \uXXXX
        escape_sequences = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t'
        ])
        # Unicode escape: \uXXXX with hex digits
        hex_digit = st.sampled_from("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: "".join(t))

        # Compose string content as a list of either safe chars or escapes
        content_piece = st.one_of(
            safe_chars.map(lambda c: c),
            escape_sequences,
            unicode_escape,
        )
        # Limit length to keep size bounded
        content = st.lists(content_piece, max_size=20).map("".join)
        return content.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # JSON numbers: use Hypothesis floats converted to JSON number strings
    # We'll generate numbers as strings matching the grammar
    def json_number():
        # Generate floats in a reasonable range, then convert to JSON number string
        # Use decimals to avoid scientific notation except for exponent part
        # We'll generate floats and format them ourselves
        def float_to_json_number(f):
            import math
            if math.isnan(f) or math.isinf(f):
                # fallback to 0 if invalid
                return "0"
            # Format float to JSON number string
            # Use repr to get a string, then fix if needed
            s = repr(f)
            # repr may produce 'inf', 'nan', or scientific notation
            # We allow scientific notation per grammar
            # Remove trailing .0 if present
            if s.endswith(".0"):
                s = s[:-2]
            return s

        return st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e10,
            max_value=1e10,
        ).map(float_to_json_number)

    json_number_st = json_number()

    # Recursive JSON values
    # We use st.recursive to build nested objects and arrays

    # Forward declaration for value strategy
    # value = STRING | NUMBER | obj | arr | true | false | null

    # Base cases: primitives
    base = st.one_of(
        json_string_st,
        json_number_st,
        json_null,
        json_true,
        json_false,
    )

    # Recursive containers
    def json_obj():
        # pair: STRING : value
        pair = st.tuples(json_string_st, value).map(lambda t: f"{t[0]}:{t[1]}")
        # object: { pair (, pair)* } or {}
        # Limit number of pairs to keep size bounded
        return st.lists(pair, max_size=5).map(
            lambda pairs: "{" + ",".join(pairs) + "}" if pairs else "{}"
        )

    def json_arr():
        # array: [ value (, value)* ] or []
        return st.lists(value, max_size=5).map(
            lambda values: "[" + ",".join(values) + "]" if values else "[]"
        )

    # Compose value recursively
    value = st.recursive(
        base,
        lambda children: st.one_of(
            json_obj(),
            json_arr(),
        ),
        max_leaves=10,
    )

    # Compose full JSON text: value + EOF
    json_text = value.map(lambda s: s)

    s = draw(json_text)
    return s.encode("utf-8")