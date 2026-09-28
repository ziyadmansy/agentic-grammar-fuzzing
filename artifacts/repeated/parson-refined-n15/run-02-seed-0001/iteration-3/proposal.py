from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then JSON-encode them to ensure correctness.
    # But since we can't use json.dumps (eval/exec forbidden), we build strings manually.
    # We'll generate strings with safe codepoints and some escapes.

    # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
    safe_chars = st.characters(
        blacklist_characters=['"', '\\'],
        blacklist_categories=('Cc',)  # control chars
    )

    # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
    # We'll mix safe chars and escapes in the string.

    def json_string_chars():
        # Either a safe char or an escape sequence
        esc_simple = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \uXXXX with hex digits
        hex_digit = st.sampled_from('0123456789abcdefABCDEF')
        esc_unicode = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))
        return st.one_of(safe_chars.map(lambda c: c), esc_simple, esc_unicode)

    # Compose string content with length bounded to keep size reasonable
    string_content = st.lists(json_string_chars(), max_size=20).map(''.join)
    json_string = string_content.map(lambda s: f'"{s}"')

    # NUMBER strategy: generate numbers as strings matching the grammar
    # We'll generate floats and ints and format them accordingly
    def number_str():
        # Generate a float or int number string
        sign = st.one_of(st.just(''), st.just('-'))
        int_part = st.one_of(st.just('0'), st.integers(min_value=1, max_value=10**6).map(str))
        frac_part = st.one_of(st.just(''), st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False).map(lambda f: f'{f:.6f}'.lstrip('0')))
        # frac_part may start with '.', so we fix that
        def fix_frac(f):
            if f == '':
                return ''
            if f.startswith('0'):
                return f[1:]
            return f
        frac_part = frac_part.map(fix_frac)
        exp_part = st.one_of(st.just(''), st.integers(min_value=-100, max_value=100).map(lambda e: f'e{e:+d}'))
        return st.tuples(sign, int_part, frac_part, exp_part).map(lambda t: ''.join(t))

    json_number = number_str()

    # Recursive JSON value strategy
    # We'll use st.recursive to build nested objects and arrays

    # Forward declaration for value
    # value = STRING | NUMBER | obj | arr | true | false | null

    # obj: '{' pair (',' pair)* '}' | '{}'
    # pair: STRING ':' value

    # arr: '[' value (',' value)* ']' | '[]'

    # We'll define pair and obj inside the recursive function

    # Define value strategy recursively
    def json_value():
        base = st.one_of(
            json_string,
            json_number,
            json_null,
            json_true,
            json_false,
        )

        # Recursive containers
        def obj_strategy():
            # pair: STRING ':' value
            pair = st.tuples(json_string, value).map(lambda p: f'{p[0]}:{p[1]}')
            pairs = st.lists(pair, max_size=5)
            return pairs.map(lambda ps: '{' + (','.join(ps) if ps else '') + '}')

        def arr_strategy():
            values = st.lists(value, max_size=5)
            return values.map(lambda vs: '[' + (','.join(vs) if vs else '') + ']')

        return st.recursive(
            base,
            lambda children: st.one_of(obj_strategy(), arr_strategy()),
            max_leaves=10,
        )

    value = json_value()

    # Compose full JSON with EOF (just ensure full consumption)
    json_full = value.map(lambda s: s)

    s = draw(json_full)
    return s.encode('utf-8')