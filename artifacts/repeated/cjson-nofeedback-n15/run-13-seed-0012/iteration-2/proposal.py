from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.builds(
        lambda n: str(n),
        st.one_of(
            st.integers(min_value=-1_000_000, max_value=1_000_000),
            st.floats(allow_infinity=False, allow_nan=False, width=32),
        ),
    )
    # STRING with escapes and safe codepoints
    # We'll generate strings with safe unicode codepoints and some escapes
    # SAFECODEPOINT: ~["\\\u0000-\u001F]
    # We'll allow codepoints from 0x20 to 0x10FFFF except backslash and quote
    def safe_char():
        # exclude " (0x22) and \ (0x5C) and control chars <0x20
        # so valid codepoints: 0x20-0x21, 0x23-0x5B, 0x5D-0x10FFFF
        # We'll generate from ranges:
        # 0x20-0x21, 0x23-0x5B, 0x5D-0x7F (ASCII printable except " and \)
        # plus some unicode above 0x7F
        ranges = [
            (0x20, 0x21),
            (0x23, 0x5B),
            (0x5D, 0x7F),
            (0x80, 0xD7FF),
            (0xE000, 0x10FFFF),
        ]
        # sample one range then sample a codepoint from it
        r = draw(st.sampled_from(ranges))
        c = draw(st.integers(min_value=r[0], max_value=r[1]))
        return chr(c)

    # ESC: \ followed by one of ["\/bfnrt] or \uXXXX
    simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
    def unicode_escape():
        hex_digits = st.text(st.characters(min_codepoint=0x30, max_codepoint=0x39) | st.characters(min_codepoint=0x41, max_codepoint=0x46) | st.characters(min_codepoint=0x61, max_codepoint=0x66), min_size=4, max_size=4)
        return hex_digits.map(lambda h: '\\u' + h)
    esc_char = st.one_of(simple_escapes, unicode_escape())

    # Compose string characters: either safe_char or escape
    # To keep it simple, generate a list of chars where each char is either safe_char or escape
    def json_string():
        # length bounded to keep output size small
        # mix safe chars and escapes
        chars = st.lists(
            st.one_of(
                st.builds(lambda c: c, safe_char()),
                esc_char,
            ),
            min_size=0,
            max_size=20,
        )
        s = draw(chars)
        return '"' + ''.join(s) + '"'

    # Compose value recursively
    # We'll use st.recursive to build nested arrays and objects
    # Base cases: string, number, true, false, null
    base = st.one_of(
        st.deferred(json_string),
        json_number,
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: array and object
    # array: '[' value (',' value)* ']' or '[]'
    # object: '{' pair (',' pair)* '}' or '{}'
    # pair: STRING ':' value

    # We'll define pair as a tuple of (string, value)
    def pair():
        k = draw(json_string())
        v = draw(value)
        return f"{k}:{v}"

    # But since pair depends on value, and value depends on pair, we must define value first as a strategy
    # We'll do this with st.recursive

    # We need to define value as a strategy, so we do a trick:
    # define a function that returns the recursive strategy

    def json_value():
        # base values
        base_values = st.one_of(
            json_string(),
            json_number,
            json_true,
            json_false,
            json_null,
        )
        # recursive containers
        def array_strategy():
            # list of values separated by commas or empty
            return st.lists(json_value(), max_size=5).map(
                lambda vs: "[" + ",".join(vs) + "]"
            )

        def object_strategy():
            # list of pairs separated by commas or empty
            # pairs: string:value
            def gen_pair():
                k = draw(json_string())
                v = draw(json_value())
                return f"{k}:{v}"
            pairs = st.lists(
                st.tuples(json_string(), json_value()),
                max_size=5,
            ).map(lambda pairs: "{" + ",".join(f"{k}:{v}" for k, v in pairs) + "}")
            return pairs

        containers = st.one_of(array_strategy(), object_strategy())

        return st.one_of(base_values, containers)

    # But the above is not valid because draw is not accessible inside map or one_of
    # So we must use st.recursive properly

    # Define base strategy for value
    base_value = st.one_of(
        json_string(),
        json_number,
        json_true,
        json_false,
        json_null,
    )

    # Recursive strategy for value
    value = st.recursive(
        base_value,
        lambda children: st.one_of(
            # array
            st.lists(children, max_size=5).map(lambda vs: "[" + ",".join(vs) + "]"),
            # object
            st.lists(
                st.tuples(json_string(), children),
                max_size=5,
            ).map(lambda pairs: "{" + ",".join(f"{k}:{v}" for k, v in pairs) + "}"),
        ),
        max_leaves=10,
    )

    # Compose the full JSON: value + EOF
    json_text = draw(value)
    return json_text.encode("utf-8")