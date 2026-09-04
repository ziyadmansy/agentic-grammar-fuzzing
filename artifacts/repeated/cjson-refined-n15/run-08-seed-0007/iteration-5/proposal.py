from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: valid JSON strings with escapes and safe codepoints
    # We'll generate strings of length 0..20 with safe chars and some escapes
    # SAFECODEPOINT: any char except " \ and control chars (U+0000-U+001F)
    # We'll include common escapes as literals
    safe_char = st.characters(
        blacklist_characters=['"', '\\'],
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    )
    # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
    # We'll generate either a safe char or an escape sequence
    def json_string_chars():
        # Escape sequences as strings
        simple_escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \uXXXX with hex digits
        hex_digit = st.characters(min_codepoint=0x30, max_codepoint=0x39).filter(lambda c: c in '0123456789abcdefABCDEF')
        unicode_escape = st.tuples(
            st.just('\\u'),
            st.sampled_from('0123456789abcdefABCDEF'),
            st.sampled_from('0123456789abcdefABCDEF'),
            st.sampled_from('0123456789abcdefABCDEF'),
            st.sampled_from('0123456789abcdefABCDEF'),
        ).map(lambda t: ''.join(t))
        return st.one_of(simple_escapes, unicode_escape, safe_char)

    json_string = st.lists(json_string_chars(), max_size=20).map(lambda chars: '"' + ''.join(chars) + '"')

    # NUMBER strategy: use Hypothesis built-in floats converted to JSON number strings
    # We'll generate numbers as strings matching the grammar
    # To keep it simple, generate integers and floats with optional exponent
    def json_number_str():
        # integer part: 0 or non-zero digit followed by digits
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        frac_part = st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False).map(lambda f: ("%.10f" % f).lstrip("0"))
        )
        # Instead of complicated float formatting, just generate floats and format as JSON numbers
        # We'll use floats from Hypothesis and format them ourselves
        float_num = st.floats(allow_nan=False, allow_infinity=False).map(lambda f: format(f, '.10g'))
        # But floats can produce scientific notation, which is allowed
        # We'll just use float_num directly
        return float_num

    json_number = json_number_str()

    # Forward declaration for recursive value
    # We'll define value recursively using st.recursive

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string,
        json_number,
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: object and array
    # We'll define them inside a function to use in st.recursive

    def json_value():
        return st.recursive(
            base_values,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.builds(
                    lambda pairs: "{" + ",".join(pairs) + "}",
                    st.lists(
                        st.tuples(json_string, children).map(lambda t: t[0] + ":" + t[1]),
                        max_size=3,
                    )
                ),
                # empty object
                st.just("{}"),
                # array: [ value (, value)* ] or []
                st.builds(
                    lambda vals: "[" + ",".join(vals) + "]",
                    st.lists(children, max_size=3)
                ),
                # empty array
                st.just("[]"),
            ),
            max_leaves=10,
        )

    json_val = json_value()

    # Compose full JSON with EOF
    json_full = json_val.map(lambda s: s)

    # Draw the JSON string and encode as bytes
    s = draw(json_full)
    return s.encode("utf-8")