from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode them as JSON strings
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and " \)
        # We'll allow some escapes as well
        # Use a small subset of unicode to keep it simple and safe
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',),
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Compose string with length 0..20
        base_str = st.text(safe_chars, max_size=20)

        # We also want to sometimes include escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        # We'll do this by randomly inserting escapes into the string
        # For simplicity, generate a list of either safe chars or escapes, then join

        escapes = st.sampled_from([
            r'\"', r'\\', r'\b', r'\f', r'\n', r'\r', r'\t',
            # Unicode escape: \uXXXX with hex digits
            lambda: r'\u' + ''.join(draw(st.sampled_from('0123456789abcdefABCDEF')) for _ in range(4))
        ])

        # Compose a list of 0..20 elements, each either a safe char or an escape string
        def element():
            # 80% safe char, 20% escape
            return st.one_of(
                safe_chars.map(lambda c: c),
                escapes.flatmap(lambda e: e() if callable(e) else st.just(e))
            )

        elements = st.lists(element(), max_size=20)
        s = draw(elements)
        # Join elements into a string
        joined = ''.join(s)
        # Wrap in quotes
        return f'"{joined}"'

    json_string_st = st.builds(lambda s: s, json_string())

    # NUMBER strategy: integers and floats with optional exponent
    json_number = st.one_of(
        st.integers(min_value=-(10**9), max_value=10**9).map(str),
        st.floats(allow_infinity=False, allow_nan=False, width=32).map(lambda f: format(f, '.6g'))
    )

    # Recursive JSON value strategy
    # We'll use st.recursive to build obj and arr

    # Forward declaration for value
    # We'll define value as a strategy that includes primitives and recursive containers

    # Base values
    base_values = st.one_of(
        json_string_st,
        json_number,
        json_null,
        json_true,
        json_false,
    )

    # To avoid too deep recursion and too large outputs, limit max depth and size
    # Compose obj and arr from smaller values

    # pair: STRING ':' value
    @st.composite
    def pair(draw):
        k = draw(json_string_st)
        v = draw(value)
        return f'{k}:{v}'

    # obj: '{' pair (',' pair)* '}' or '{}'
    @st.composite
    def obj(draw):
        # Choose number of pairs 0..4 to keep size bounded
        n = draw(st.integers(min_value=0, max_value=4))
        if n == 0:
            return '{}'
        pairs = [draw(pair) for _ in range(n)]
        return '{' + ','.join(pairs) + '}'

    # arr: '[' value (',' value)* ']' or '[]'
    @st.composite
    def arr(draw):
        n = draw(st.integers(min_value=0, max_value=4))
        if n == 0:
            return '[]'
        values = [draw(value) for _ in range(n)]
        return '[' + ','.join(values) + ']'

    # Now define value as recursive
    value = st.recursive(
        base_values,
        lambda children: st.one_of(
            obj(),
            arr(),
        ),
        max_leaves=10,
    )

    # Compose full json: value EOF
    json_text = value

    s = draw(json_text)
    return s.encode('utf-8')