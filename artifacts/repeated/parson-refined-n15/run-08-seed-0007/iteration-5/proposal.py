from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    # STRING: produce valid JSON strings with escapes and safe codepoints
    # We'll produce Python strings and then json.dumps them to ensure correctness,
    # but since we cannot import json or eval, we build strings manually.
    # Instead, produce strings with safe codepoints and escapes manually.
    # We'll produce strings of safe unicode codepoints excluding control chars and quotes/backslash.
    # To keep it simple, produce strings of ASCII printable except " and \, plus some escapes.
    safe_chars = st.characters(
        blacklist_characters=['\\', '"', '\u0000', '\u0001', '\u0002', '\u0003', '\u0004', '\u0005', '\u0006', '\u0007',
                              '\u0008', '\u000b', '\u000c', '\u000e', '\u000f', '\u0010', '\u0011', '\u0012', '\u0013',
                              '\u0014', '\u0015', '\u0016', '\u0017', '\u0018', '\u0019', '\u001a', '\u001b', '\u001c',
                              '\u001d', '\u001e', '\u001f', '"', '\\'],
        min_codepoint=0x20,
        max_codepoint=0x7E,
    )
    # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
    # We'll produce strings that may contain these escapes randomly.
    # To keep it simple, produce strings of safe_chars and occasionally insert escapes.
    def json_string_chars():
        # 80% safe_chars, 20% escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape \uXXXX with hex digits
        hex_digit = st.sampled_from('0123456789abcdefABCDEF')
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))
        escape_or_unicode = st.one_of(escapes, unicode_escape)
        return st.one_of(safe_chars.map(lambda c: c), escape_or_unicode)
    # Compose string of length 0..20
    json_string = st.lists(json_string_chars(), max_size=20).map(lambda cs: '"' + ''.join(cs) + '"')

    # NUMBER: produce valid JSON numbers
    # Use Hypothesis floats converted to strings with JSON number format
    # We'll produce strings matching the grammar:
    # '-'? INT ('.' [0-9]+)? EXP?
    # INT: '0' or non-zero digit followed by digits
    # EXP: [Ee][+-]?[0-9]+
    def json_number():
        # INT part
        def int_part():
            return st.one_of(
                st.just("0"),
                st.tuples(
                    st.sampled_from("123456789"),
                    st.text("0123456789", max_size=10)
                ).map(lambda t: t[0] + t[1])
            )
        # Fractional part
        frac_part = st.one_of(st.just(""), st.tuples(st.just("."), st.text("0123456789", min_size=1, max_size=10)).map(lambda t: t[0] + t[1]))
        # Exponent part
        exp_sign = st.one_of(st.just("+"), st.just("-"), st.just(""))
        exp_part = st.one_of(st.just(""), st.tuples(st.sampled_from("Ee"), exp_sign, st.text("0123456789", min_size=1, max_size=5)).map(lambda t: t[0] + t[1] + t[2]))
        # Optional minus sign
        sign = st.one_of(st.just(""), st.just("-"))
        return st.tuples(sign, int_part(), frac_part, exp_part).map(lambda t: t[0] + t[1] + t[2] + t[3])

    # Recursive JSON value strategy
    # To keep recursion bounded, limit max depth to 3
    # Compose obj, arr, and primitives
    # obj: '{' pair (',' pair)* '}' or '{}'
    # pair: STRING ':' value
    # arr: '[' value (',' value)* ']' or '[]'

    # Forward declaration for recursion
    json_value = st.deferred(lambda: json_value_inner)

    # pair strategy
    @st.composite
    def pair(draw):
        k = draw(json_string)
        v = draw(json_value)
        return k + ":" + v

    # obj strategy
    @st.composite
    def obj(draw):
        # Empty or 1..4 pairs
        n = draw(st.integers(min_value=0, max_value=4))
        if n == 0:
            return "{}"
        pairs = draw(st.lists(pair(), min_size=n, max_size=n))
        return "{" + ",".join(pairs) + "}"

    # arr strategy
    @st.composite
    def arr(draw):
        n = draw(st.integers(min_value=0, max_value=4))
        if n == 0:
            return "[]"
        values = draw(st.lists(json_value, min_size=n, max_size=n))
        return "[" + ",".join(values) + "]"

    # Compose json_value_inner with bounded recursion depth
    # Use st.recursive to limit depth and size
    json_value_inner = st.recursive(
        st.one_of(
            json_string,
            json_number(),
            json_null,
            json_true,
            json_false,
        ),
        lambda children: st.one_of(
            obj(),
            arr(),
        ),
        max_leaves=10,
    )

    # Compose full json text with EOF
    json_text = draw(json_value_inner)
    # Return bytes
    return json_text.encode("utf-8")