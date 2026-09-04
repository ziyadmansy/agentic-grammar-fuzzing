from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # SAFECODEPOINT: any Unicode codepoint except control chars and " \ 
    # We'll restrict to BMP and exclude control chars and backslash and quote
    def json_string_chars():
        # safe chars: codepoints 0x20-0x21, 0x23-0x5B, 0x5D-0x10FFFF excluding backslash and quote
        # but Hypothesis doesn't support > 0xFFFF in characters easily, so limit to BMP
        # We'll exclude control chars (0x00-0x1F), quote (0x22), backslash (0x5C)
        safe_chars = (
            [chr(c) for c in range(0x20, 0x22)] +
            [chr(c) for c in range(0x23, 0x5C)] +
            [chr(c) for c in range(0x5D, 0x7F)]
        )
        return st.sampled_from(safe_chars)

    # Escape sequences: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
    escape_simple = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
    # \uXXXX: 4 hex digits
    hex_digit = st.sampled_from("0123456789abcdefABCDEF")
    escape_unicode = st.builds(
        lambda h1, h2, h3, h4: "\\u" + h1 + h2 + h3 + h4,
        hex_digit, hex_digit, hex_digit, hex_digit
    )
    escape_seq = st.one_of(escape_simple, escape_unicode)

    # Compose string content: mix of safe chars and escapes
    # To keep near-valid, allow some escapes and safe chars
    def string_content():
        # Each char is either safe char or escape sequence
        return st.lists(
            st.one_of(json_string_chars(), escape_seq),
            min_size=0,
            max_size=20
        ).map("".join)

    json_string = string_content().map(lambda s: f'"{s}"')

    # NUMBER strategy: use Hypothesis floats and ints, then format as JSON number string
    # We'll produce numbers as strings matching the grammar
    def json_number():
        # Generate int part
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        # Optional fraction part
        frac_part = st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)
            .map(lambda f: ("%.10f" % f).lstrip("0") if f > 0 else "")
            .filter(lambda s: s == "" or s.startswith("."))
        )
        # Optional exponent part
        exp_part = st.one_of(
            st.just(""),
            st.integers(min_value=-100, max_value=100).map(lambda e: "e%d" % e)
        )
        # Optional minus sign
        sign = st.one_of(st.just(""), st.just("-"))
        return st.tuples(sign, int_part, frac_part, exp_part).map(
            lambda t: "".join(t)
        ).filter(lambda s: s != "")

    # To simplify, use Hypothesis built-in decimal strings for numbers
    json_number = st.one_of(
        st.integers(min_value=-(10**6), max_value=10**6).map(str),
        st.floats(min_value=-1e6, max_value=1e6, allow_infinity=False, allow_nan=False)
        .map(lambda f: format(f, ".10g"))
    )

    # Forward declarations for recursive structures
    # We'll use st.recursive to build JSON values

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string,
        json_number,
        json_true,
        json_false,
        json_null,
    )

    # Recursive JSON value strategy
    def json_value():
        # Use recursive to build arrays and objects
        return st.recursive(
            base_values,
            lambda children: st.one_of(
                # array: [ value (, value)* ]
                st.lists(children, min_size=0, max_size=5).map(
                    lambda vs: "[" + ",".join(vs) + "]"
                ),
                # object: { pair (, pair)* } or empty {}
                st.dictionaries(
                    keys=json_string,
                    values=children,
                    min_size=0,
                    max_size=5,
                ).map(
                    lambda d: (
                        "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"
                        if d else "{}"
                    )
                ),
            ),
            max_leaves=10,
        )

    json_full = json_value()

    s = draw(json_full)
    return s.encode("utf-8")