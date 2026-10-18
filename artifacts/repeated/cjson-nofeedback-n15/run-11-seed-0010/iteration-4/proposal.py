from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: simple ASCII strings with escapes
    # We'll generate strings without control chars except those escaped
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escape sequences: \", \\, \b, \f, \n, \r, \t, \uXXXX
        escape_sequences = st.sampled_from([
            r'\"', r'\\', r'\b', r'\f', r'\n', r'\r', r'\t',
        ])
        # Unicode escape \uXXXX
        def unicode_escape():
            hex_digit = st.sampled_from('0123456789abcdefABCDEF')
            return st.tuples(hex_digit, hex_digit, hex_digit, hex_digit).map(
                lambda t: r'\u' + ''.join(t)
            )
        escape_seq = st.one_of(escape_sequences, unicode_escape())

        # Compose string content: mix safe chars and escapes
        # We'll generate a list of length 0..20 of either safe char or escape sequence
        content = st.lists(
            st.one_of(
                safe_chars.map(lambda c: c),
                escape_seq,
            ),
            max_size=20,
        ).map(''.join)

        return content.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # NUMBER strategy: use Hypothesis built-in floats and ints, then format as JSON number
    # We'll generate numbers as strings matching the grammar
    def json_number():
        # Generate floats and ints, then convert to JSON number string
        # Limit magnitude to avoid huge exponents
        number = st.one_of(
            st.integers(min_value=-10**6, max_value=10**6),
            st.floats(
                allow_infinity=False,
                allow_nan=False,
                width=32,
                min_value=-1e6,
                max_value=1e6,
            ),
        )
        def to_json_number(n):
            # Format float with minimal representation
            if isinstance(n, int):
                return str(n)
            else:
                # Use repr to get a JSON-compatible float string
                s = repr(n)
                # Ensure exponent uses 'e' not 'E'
                s = s.replace('E', 'e')
                # Remove trailing + in exponent if any
                s = s.replace('e+', 'e')
                return s
        return number.map(to_json_number)

    json_number_st = json_number()

    # Forward declarations for recursive structures
    # We'll use st.recursive to build value

    # Define value strategy recursively
    def json_value():
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_null,
            json_true,
            json_false,
        )
        # Recursive containers: obj and arr
        def json_obj():
            # pair: STRING ':' value
            pair = st.tuples(json_string_st, json_value()).map(
                lambda t: f'{t[0]}:{t[1]}'
            )
            # object: '{' pair (',' pair)* '}' or '{}'
            # Limit number of pairs to keep size bounded
            pairs = st.lists(pair, max_size=5)
            return pairs.map(
                lambda ps: '{' + (','.join(ps) if ps else '') + '}'
            )

        def json_arr():
            # array: '[' value (',' value)* ']' or '[]'
            values = st.lists(json_value(), max_size=5)
            return values.map(
                lambda vs: '[' + (','.join(vs) if vs else '') + ']'
            )

        return st.recursive(
            base,
            lambda children: st.one_of(json_obj(), json_arr()),
            max_leaves=10,
        )

    value_st = json_value()

    # Compose full JSON: value + EOF
    json_st = value_st.map(lambda s: s)

    s = draw(json_st)
    return s.encode('utf-8')