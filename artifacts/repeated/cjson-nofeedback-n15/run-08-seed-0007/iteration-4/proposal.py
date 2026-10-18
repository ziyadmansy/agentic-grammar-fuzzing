from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We limit length to keep size bounded
    def json_string():
        # Characters allowed inside strings: safe codepoints and escapes
        # We'll generate unicode codepoints excluding control chars and quotes/backslash
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escape sequences: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t'
        ])
        # Unicode escape: \u followed by 4 hex digits
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.builds(
            lambda h1,h2,h3,h4: r'\u' + h1 + h2 + h3 + h4,
            hex_digit, hex_digit, hex_digit, hex_digit
        )
        escape_seq = st.one_of(escapes, unicode_escape)
        # Compose string content from safe chars and escapes
        # Mix safe chars and escapes
        chunk = st.one_of(safe_char, escape_seq)
        # Limit length to keep size bounded
        content = st.lists(chunk, min_size=0, max_size=20).map("".join)
        return content.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # NUMBER strategy: use Hypothesis built-in floats converted to JSON number strings
    # We'll generate numbers as strings matching the grammar
    def json_number():
        # Generate floats in a reasonable range, then convert to JSON number strings
        # Avoid infinities and NaNs
        # Use decimal.Decimal to get canonical string representation
        import decimal
        def float_to_json_number(f):
            # Convert float to decimal string without scientific notation if possible
            d = decimal.Decimal(str(f))
            # Format to remove trailing zeros and exponent if possible
            s = format(d.normalize(), 'f')
            # If s is empty or just '-', fallback to '0'
            if s == '' or s == '-':
                s = '0'
            return s
        return st.floats(
            allow_nan=False, allow_infinity=False,
            width=32,  # limit size
            min_value=-1e10, max_value=1e10
        ).map(float_to_json_number)

    json_number_st = json_number()

    # Forward declaration for recursive structures
    # We'll define value recursively below

    # Recursive JSON value strategy
    def json_value():
        # Base cases: string, number, true, false, null
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_true,
            json_false,
            json_null,
        )

        # Recursive cases: object and array
        # Use st.recursive to keep recursion bounded
        def obj_strategy():
            # pair: STRING ':' value
            pair = st.tuples(json_string_st, json_value()).map(lambda p: f"{p[0]}:{p[1]}")
            # object: '{' pair (',' pair)* '}' or '{}'
            # limit number of pairs to keep size bounded
            pairs = st.lists(pair, max_size=5)
            return pairs.map(lambda ps: "{" + ",".join(ps) + "}" if ps else "{}")

        def arr_strategy():
            # array: '[' value (',' value)* ']' or '[]'
            values = st.lists(json_value(), max_size=5)
            return values.map(lambda vs: "[" + ",".join(vs) + "]" if vs else "[]")

        return st.recursive(
            base,
            lambda children: st.one_of(obj_strategy(), arr_strategy()),
            max_leaves=10,
        )

    # Compose full JSON text with EOF
    json_text = json_value().map(lambda s: s)

    # Draw one example and encode as bytes
    s = draw(json_text)
    return s.encode("utf-8")