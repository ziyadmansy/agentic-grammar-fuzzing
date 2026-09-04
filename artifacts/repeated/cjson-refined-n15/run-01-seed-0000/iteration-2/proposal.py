from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON tokens
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # SAFECODEPOINT: any char except " \ and control chars (U+0000-U+001F)
    # We'll generate unicode characters excluding control chars and " and \
    def json_string_chars():
        # Unicode codepoints excluding control chars and " and \
        # Control chars: 0x00-0x1F
        # Exclude " (0x22) and \ (0x5C)
        # We'll use characters from 0x20 to 0x10FFFF excluding 0x22 and 0x5C
        # To keep it simple, limit to BMP (0x20-0xD7FF and 0xE000-0xFFFF)
        # and exclude 0x22 and 0x5C
        def char_filter(c):
            return (
                (0x20 <= ord(c) <= 0xD7FF or 0xE000 <= ord(c) <= 0xFFFF)
                and c not in ('"', '\\')
            )
        return st.characters(whitelist_categories=('Lu','Ll','Nd','Zs','Po','Ps','Pe','Sm','Sc','Sk','So'),
                             blacklist_characters=['"', '\\']) | st.just(' ')  # add space explicitly

    # Escape sequences: \" \\ \/ \b \f \n \r \t and \uXXXX
    # We'll produce strings that may contain escapes by mixing raw chars and escapes
    # To keep it simple, generate strings with raw safe chars and some escapes

    # Escape sequences as strings
    escapes = st.sampled_from([
        r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t'
    ])

    # Unicode escape: \uXXXX where X is hex digit
    hex_digit = st.characters("0123456789abcdefABCDEF", min_codepoint=0, max_codepoint=0x7F)
    unicode_escape = st.tuples(
        st.just(r'\u'),
        st.text("0123456789abcdefABCDEF", min_size=4, max_size=4)
    ).map(lambda t: t[0] + t[1])

    # Compose a character or escape sequence
    json_string_char = st.one_of(
        json_string_chars().filter(lambda c: c not in ['"', '\\']),
        escapes,
        unicode_escape,
    )

    # Generate string content with length 0 to 20
    string_content = st.text(alphabet=json_string_char, min_size=0, max_size=20)

    json_string = string_content.map(lambda s: '"' + s + '"')

    # NUMBER strategy: produce valid JSON numbers
    # Use Hypothesis built-in floats converted to JSON number strings
    # But restrict to finite numbers and avoid infinities and NaNs
    def json_number_str():
        # Generate numbers as strings matching NUMBER grammar
        # We'll generate integers and floats with optional exponent
        # To keep it bounded, generate strings directly
        sign = st.one_of(st.just(''), st.just('-'))
        int_part = st.one_of(
            st.just('0'),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        frac_part = st.one_of(st.just(''), st.floats(min_value=0, max_value=1).map(lambda f: '.' + str(f)[2:]))
        exp_part = st.one_of(
            st.just(''),
            st.tuples(
                st.sampled_from(['e', 'E']),
                st.one_of(st.just(''), st.sampled_from(['+', '-'])),
                st.integers(min_value=0, max_value=99).map(lambda x: str(x))
            ).map(lambda t: t[0] + t[1] + t[2])
        )
        return st.tuples(sign, int_part, frac_part, exp_part).map(lambda t: ''.join(t))

    json_number = json_number_str()

    # Forward declaration for recursive value
    # We'll use st.recursive to build values

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string,
        json_number,
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: obj and arr
    # We'll limit recursion depth and size to keep output bounded

    # Pair: STRING ':' value
    @st.composite
    def pair(draw):
        k = draw(json_string)
        v = draw(value)
        return k + ':' + v

    # Object: '{' pair (',' pair)* '}' or '{}'
    @st.composite
    def obj(draw):
        # Generate 0 to 5 pairs
        n = draw(st.integers(min_value=0, max_value=5))
        if n == 0:
            return '{}'
        pairs = [draw(pair) for _ in range(n)]
        return '{' + ','.join(pairs) + '}'

    # Array: '[' value (',' value)* ']' or '[]'
    @st.composite
    def arr(draw):
        n = draw(st.integers(min_value=0, max_value=5))
        if n == 0:
            return '[]'
        values = [draw(value) for _ in range(n)]
        return '[' + ','.join(values) + ']'

    # Recursive value strategy
    value = st.recursive(
        base_values,
        lambda children: st.one_of(
            obj(),
            arr(),
        ),
        max_leaves=10,
    )

    # Compose full JSON text: value EOF
    json_text = value

    s = draw(json_text)
    return s.encode('utf-8')