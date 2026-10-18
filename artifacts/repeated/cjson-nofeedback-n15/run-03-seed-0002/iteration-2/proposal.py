from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escapes: \" \\ \/ \b \f \n \r \t and unicode \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t'
        ])
        # Unicode escape \uXXXX with hex digits
        unicode_escape = st.builds(
            lambda h1,h2,h3,h4: r'\u' + h1 + h2 + h3 + h4,
            st.sampled_from('0123456789abcdefABCDEF'),
            st.sampled_from('0123456789abcdefABCDEF'),
            st.sampled_from('0123456789abcdefABCDEF'),
            st.sampled_from('0123456789abcdefABCDEF'),
        )
        char = st.one_of(safe_char, escapes, unicode_escape)
        # Compose string content with length 0..20
        content = st.text(characters=char, min_size=0, max_size=20)
        return content.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # NUMBER strategy: integers, floats, exponents
    json_number = st.one_of(
        # Integer
        st.integers(min_value=-(10**6), max_value=10**6).map(str),
        # Float with decimal part
        st.floats(allow_infinity=False, allow_nan=False, width=32).map(lambda f: format(f, 'g')),
        # Scientific notation
        st.tuples(
            st.floats(allow_infinity=False, allow_nan=False, width=32),
            st.integers(min_value=-10, max_value=10)
        ).map(lambda t: f"{format(t[0], 'g')}e{t[1]}")
    )

    # Forward declaration for recursive structures
    # We'll define value recursively below

    # Recursive JSON value strategy
    def json_value():
        # Base cases: primitives
        base = st.one_of(
            json_string_st,
            json_number,
            json_null,
            json_true,
            json_false,
        )

        # Recursive cases: object and array
        # To keep size bounded, limit max depth and max elements
        max_depth = 3
        max_pairs = 5
        max_elements = 5

        def obj_strategy():
            # pair: STRING ':' value
            pair = st.tuples(json_string_st, value).map(lambda p: f"{p[0]}:{p[1]}")
            pairs = st.lists(pair, max_size=max_pairs)
            return pairs.map(lambda ps: "{" + ",".join(ps) + "}")

        def arr_strategy():
            elems = st.lists(value, max_size=max_elements)
            return elems.map(lambda es: "[" + ",".join(es) + "]")

        return st.recursive(
            base,
            lambda children: st.one_of(
                obj_strategy(),
                arr_strategy(),
            ),
            max_leaves=50,
        )

    value = json_value()

    # Compose full JSON with EOF (just the value here)
    json_bytes = draw(value).encode("utf-8")
    return json_bytes