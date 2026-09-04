from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly matching grammar, with safe codepoints and escapes
    # We allow near-valid strings by including some escapes and safe codepoints.
    # Limit length to keep size bounded.
    def json_string():
        # safe codepoints excluding control chars and quotes/backslash
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # escapes allowed: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # unicode escape \uXXXX with hex digits
        hex_digit = st.sampled_from('0123456789abcdefABCDEF')
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))
        escape = st.one_of(simple_escapes, unicode_escape)
        # string content: mix of safe chars and escapes
        # To allow near-valid, allow some escapes and safe chars mixed
        string_char = st.one_of(safe_char, escape)
        # length bounded to keep output size reasonable
        content = st.lists(string_char, min_size=0, max_size=20).map(''.join)
        return content.map(lambda s: f'"{s}"')

    # NUMBER: roughly matching grammar, bounded length
    def json_number():
        # integer part
        int_part = st.one_of(
            st.just("0"),
            st.tuples(
                st.sampled_from("123456789"),
                st.text(min_size=0, max_size=5, alphabet=st.characters(min_codepoint=48, max_codepoint=57))
            ).map(lambda t: t[0] + t[1])
        )
        # fraction part optional
        fraction = st.one_of(st.just(""), st.tuples(st.just("."), st.text(min_size=1, max_size=5, alphabet=st.characters(min_codepoint=48, max_codepoint=57))).map(lambda t: t[0] + t[1]))
        # exponent part optional
        exp_sign = st.one_of(st.just("+"), st.just("-"), st.just(""))
        exponent = st.one_of(
            st.just(""),
            st.tuples(st.sampled_from("eE"), exp_sign, st.text(min_size=1, max_size=3, alphabet=st.characters(min_codepoint=48, max_codepoint=57))).map(lambda t: t[0] + t[1] + t[2])
        )
        # optional leading minus
        sign = st.one_of(st.just(""), st.just("-"))
        return st.tuples(sign, int_part, fraction, exponent).map(lambda t: ''.join(t))

    # Forward declaration for recursive structures
    # Use st.recursive to keep recursion bounded and balanced
    def json_value():
        # primitives
        primitives = st.one_of(
            json_string(),
            json_number(),
            json_true,
            json_false,
            json_null,
        )
        # recursive containers: obj and arr
        # obj: { pair (, pair)* } or {}
        # pair: STRING : value
        # arr: [ value (, value)* ] or []
        # To keep size bounded, limit number of pairs/elements

        # pair strategy
        def pair():
            return st.tuples(json_string(), st.just(":"), json_value()).map(lambda t: t[0] + t[1] + t[2])

        # object strategy
        obj = st.one_of(
            st.just("{}"),
            st.lists(pair(), min_size=1, max_size=4).map(lambda pairs: "{" + ",".join(pairs) + "}")
        )

        # array strategy
        arr = st.one_of(
            st.just("[]"),
            st.lists(json_value(), min_size=1, max_size=4).map(lambda values: "[" + ",".join(values) + "]")
        )

        return st.one_of(primitives, obj, arr)

    # Use recursive to allow nested objects and arrays with bounded depth
    json_val = st.recursive(
        st.one_of(
            json_string(),
            json_number(),
            json_true,
            json_false,
            json_null,
        ),
        lambda children: st.one_of(
            st.lists(children, min_size=1, max_size=4).map(lambda vals: "[" + ",".join(vals) + "]"),
            st.lists(
                st.tuples(json_string(), children),
                min_size=1,
                max_size=4
            ).map(lambda pairs: "{" + ",".join(k + ":" + v for k, v in pairs) + "}")
        ),
        max_leaves=10,
    )

    s = draw(json_val)
    return s.encode("utf-8")