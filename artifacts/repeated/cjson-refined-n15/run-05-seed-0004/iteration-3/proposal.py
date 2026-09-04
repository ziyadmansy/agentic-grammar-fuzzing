from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: produce valid JSON strings with escapes and safe codepoints
    # SAFECODEPOINT: ~["\\\u0000-\u001F]
    # We'll produce strings with safe unicode codepoints excluding control chars and quotes/backslash
    def json_string():
        # Characters excluding control chars, quote, backslash
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escape sequences: \" \\ \/ \b \f \n \r \t and \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t'
        ])
        # Unicode escape \uXXXX
        hex_digit = st.sampled_from("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: "".join(t))

        # Mix safe chars and escapes/unicode escapes
        # To keep it simple, generate a list of either safe chars or escapes/unicode escapes
        chunk = st.one_of(
            safe_char.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Generate string length between 0 and 30 to keep size bounded
        s = draw(st.lists(chunk, min_size=0, max_size=30))
        return '"' + "".join(s) + '"'

    json_string_st = st.deferred(json_string)

    # NUMBER: follow grammar: '-'? INT ('.' [0-9]+)? EXP?
    # INT: '0' | [1-9][0-9]*
    # EXP: [Ee][+-]?[0-9]+
    def json_number():
        # INT
        zero = st.just("0")
        nonzero_int = st.tuples(
            st.sampled_from("123456789"),
            st.text("0123456789", min_size=0, max_size=5)
        ).map(lambda t: t[0] + t[1])
        int_part = st.one_of(zero, nonzero_int)

        # Fractional part
        frac_part = st.one_of(
            st.just(""),
            st.tuples(st.just("."), st.text("0123456789", min_size=1, max_size=5)).map(lambda t: t[0] + t[1])
        )

        # Exponent part
        exp_sign = st.one_of(st.just("+"), st.just("-"), st.just(""))
        exp_part = st.one_of(
            st.just(""),
            st.tuples(
                st.sampled_from("Ee"),
                exp_sign,
                st.text("0123456789", min_size=1, max_size=3)
            ).map(lambda t: t[0] + t[1] + t[2])
        )

        # Optional minus
        sign = st.one_of(st.just(""), st.just("-"))

        return st.tuples(sign, int_part, frac_part, exp_part).map(lambda t: "".join(t))

    json_number_st = st.deferred(json_number)

    # Recursive JSON value
    # We'll use st.recursive to build nested objects and arrays with bounded depth and size

    # Forward declaration for value
    value = st.deferred(lambda: value_st)

    # pair: STRING ':' value
    @st.composite
    def pair(draw):
        k = draw(json_string_st)
        v = draw(value)
        return f"{k}:{v}"

    # obj: '{' pair (',' pair)* '}' | '{}'
    @st.composite
    def obj(draw):
        # To keep size bounded, max 0-5 pairs
        n = draw(st.integers(min_value=0, max_value=5))
        if n == 0:
            return "{}"
        pairs = [draw(pair) for _ in range(n)]
        return "{" + ",".join(pairs) + "}"

    # arr: '[' value (',' value)* ']' | '[]'
    @st.composite
    def arr(draw):
        n = draw(st.integers(min_value=0, max_value=5))
        if n == 0:
            return "[]"
        values = [draw(value) for _ in range(n)]
        return "[" + ",".join(values) + "]"

    # Compose value strategy with recursion
    value_st = st.recursive(
        st.one_of(
            json_string_st,
            json_number_st,
            json_true,
            json_false,
            json_null,
        ),
        lambda children: st.one_of(
            obj(),
            arr(),
        ),
        max_leaves=10,
    )

    # Compose full json: value EOF
    json_text = value_st.map(lambda s: s)

    s = draw(json_text)
    return s.encode("utf-8")