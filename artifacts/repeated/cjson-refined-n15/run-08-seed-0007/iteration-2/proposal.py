from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: valid JSON strings with escapes and safe codepoints
    # We'll generate strings of length 0 to 20 for bounded size
    # Escape sequences: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
    # To keep it simple, generate unicode codepoints excluding control chars and quotes/backslash
    # plus some escapes

    # Characters allowed inside JSON strings (excluding control chars and " \)
    safe_char = st.characters(
        blacklist_characters=['"', '\\'],
        blacklist_categories=('Cc',)  # Control chars
    )

    # Escape sequences as strings
    escapes = st.sampled_from([
        r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t'
    ])

    # Unicode escape \uXXXX
    def unicode_escape():
        hex_digit = st.sampled_from('0123456789abcdefABCDEF')
        return st.tuples(hex_digit, hex_digit, hex_digit, hex_digit).map(
            lambda hs: r'\u' + ''.join(hs)
        )

    # Compose string content: either safe_char or escape sequences
    string_char = st.one_of(
        safe_char.map(lambda c: c),
        escapes,
        unicode_escape()
    )

    # Generate string content length 0 to 20
    string_content = st.lists(string_char, max_size=20).map(''.join)

    json_string = string_content.map(lambda s: f'"{s}"')

    # NUMBER strategy: use Hypothesis built-in floats converted to JSON number strings
    # But JSON numbers do not allow NaN or Infinity, so we filter those out
    # Also generate integers and floats with optional exponent

    def number_to_json(n: float) -> str:
        # Format number as JSON number string
        # Use repr to get shortest representation
        # Avoid scientific notation for small integers
        if n == float('inf') or n == float('-inf') or n != n:
            # Should not happen due to filtering
            return "0"
        # Use repr, but for integers avoid trailing .0
        if int(n) == n:
            return str(int(n))
        else:
            return repr(n)

    json_number = st.floats(
        allow_infinity=False,
        allow_nan=False,
        width=32,
        min_value=-1e10,
        max_value=1e10,
    ).map(number_to_json)

    # Forward declaration for recursive structures
    # We'll define value recursively

    # Use st.deferred to allow recursion
    @st.composite
    def json_value(draw):
        # Compose value from primitives and recursive containers
        # Limit recursion depth by max_leaves parameter in recursive
        return draw(
            st.recursive(
                st.one_of(json_string, json_number, json_null, json_true, json_false),
                lambda children: st.one_of(
                    # object: { pair (, pair)* } or {}
                    st.builds(
                        lambda pairs: "{" + ",".join(pairs) + "}" if pairs else "{}",
                        st.lists(
                            st.tuples(json_string, children).map(lambda t: f"{t[0]}:{t[1]}"),
                            max_size=3,
                        )
                    ),
                    # array: [ value (, value)* ] or []
                    st.builds(
                        lambda values: "[" + ",".join(values) + "]" if values else "[]",
                        st.lists(children, max_size=3),
                    ),
                ),
                max_leaves=10,
            )
        )

    # Compose full JSON text: value EOF
    json_text = json_value()

    s = draw(json_text)
    return s.encode("utf-8")