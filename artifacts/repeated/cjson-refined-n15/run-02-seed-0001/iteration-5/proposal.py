from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic leaf strategies
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly matching JSON string with escapes and safe codepoints
    # We'll generate Python strings and then encode to JSON string literals
    def json_string():
        # safe codepoints: exclude control chars and " and \
        # We'll generate unicode strings excluding control chars and quotes/backslash
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # limit length to keep size bounded
        base_str = st.text(safe_chars, min_size=0, max_size=20)

        # Add escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        # We'll randomly replace some chars with escapes
        def escape_char(c):
            escapes = {
                '"': r'\"',
                '\\': r'\\',
                '\b': r'\b',
                '\f': r'\f',
                '\n': r'\n',
                '\r': r'\r',
                '\t': r'\t',
            }
            if c in escapes:
                return escapes[c]
            # For control chars (0x00-0x1F), encode as \uXXXX
            if ord(c) < 0x20:
                return '\\u%04x' % ord(c)
            return c

        def to_json_string(s):
            # Escape " and \ and control chars
            res = []
            for ch in s:
                res.append(escape_char(ch))
            return '"' + ''.join(res) + '"'

        return base_str.map(to_json_string)

    json_string_st = json_string()

    # NUMBER: generate JSON numbers as strings
    # We'll generate floats and ints and format them as JSON numbers
    def json_number():
        # Generate int or float or exponent form
        # Use floats with limited magnitude and digits
        # Also generate ints
        int_part = st.integers(min_value=-10**6, max_value=10**6)
        frac_part = st.floats(min_value=1e-6, max_value=1e6, allow_infinity=False, allow_nan=False)
        # We'll generate either int or float
        def to_json_num(x):
            # Format int or float to JSON number string
            if isinstance(x, int):
                return str(x)
            else:
                # Format float with minimal digits, no trailing zeros
                s = format(x, '.15g')
                # Ensure decimal point if float
                if '.' not in s and 'e' not in s and 'E' not in s:
                    s += '.0'
                return s

        return st.one_of(
            int_part.map(to_json_num),
            frac_part.map(to_json_num),
        )

    json_number_st = json_number()

    # Forward declare value strategy for recursion
    # We'll use st.recursive to build obj and arr

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string_st,
        json_number_st,
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: obj and arr
    # To keep size bounded, limit max depth and max elements

    def json_obj(children):
        # obj : '{' pair (',' pair)* '}' | '{}'
        # pair : STRING ':' value
        # Generate dict with 0 to 5 pairs
        # Keys are strings (without escapes for simplicity)
        # Values are children (value)
        keys = st.lists(
            st.text(
                st.characters(
                    blacklist_characters=['"', '\\', '\u0000', '\u001F'],
                    min_codepoint=0x20,
                    max_codepoint=0x10FFFF,
                ),
                min_size=1,
                max_size=10,
            ),
            min_size=0,
            max_size=5,
            unique=True,
        )
        def to_obj(klist, vlist):
            # Build JSON object string
            pairs = []
            for k, v in zip(klist, vlist):
                # JSON string key: escape quotes and backslash
                esc_key = k.replace('\\', '\\\\').replace('"', '\\"')
                pairs.append(f'"{esc_key}":{v}')
            return '{' + ','.join(pairs) + '}'

        return st.builds(
            to_obj,
            keys,
            st.lists(children, min_size=0, max_size=5),
        )

    def json_arr(children):
        # arr : '[' value (',' value)* ']' | '[]'
        # Generate list of 0 to 5 elements
        return st.lists(children, min_size=0, max_size=5).map(
            lambda vs: '[' + ','.join(vs) + ']'
        )

    json_value = st.recursive(
        base_values,
        lambda children: st.one_of(
            json_obj(children),
            json_arr(children),
        ),
        max_leaves=10,
    )

    # Compose full JSON text: value + EOF
    json_text = json_value

    s = draw(json_text)
    return s.encode('utf-8')