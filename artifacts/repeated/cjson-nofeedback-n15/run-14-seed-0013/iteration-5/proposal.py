from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: roughly follow grammar STRING = '"' (ESC | SAFECODEPOINT)* '"'
    # We'll allow simple escapes and safe unicode codepoints excluding control chars and quotes/backslash
    # To keep it simple, generate unicode strings excluding control chars and quotes/backslash,
    # and occasionally insert simple escapes.
    def json_string():
        # safe codepoints: exclude control chars (0x00-0x1F), quote (0x22), backslash (0x5C)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # simple escapes: \", \\, \b, \f, \n, \r, \t
        escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # unicode escape: \uXXXX
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))
        # mix safe chars and escapes/unicode escapes
        chunk = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # generate a string of length 0..20
        s = draw(st.lists(chunk, max_size=20))
        return '"' + ''.join(s) + '"'

    json_string_st = st.deferred(lambda: st.builds(lambda s: s, json_string()))

    # NUMBER strategy: follow grammar NUMBER = '-'? INT ('.' [0-9]+)? EXP?
    # We'll generate numbers as strings matching the grammar
    def json_number():
        # INT
        int_part = st.one_of(
            st.just("0"),
            st.tuples(
                st.characters(min_codepoint='1', max_codepoint='9'),
                st.text(st.characters(min_codepoint='0', max_codepoint='9'), max_size=5)
            ).map(lambda t: t[0] + t[1])
        )
        # Fractional part
        frac_part = st.one_of(
            st.none(),
            st.text(st.characters(min_codepoint='0', max_codepoint='9'), min_size=1, max_size=5).map(lambda s: '.' + s)
        )
        # Exponent part
        exp_sign = st.one_of(st.just('+'), st.just('-'), st.just(''))
        exp_part = st.one_of(
            st.none(),
            st.tuples(
                st.sampled_from(['E', 'e']),
                exp_sign,
                st.text(st.characters(min_codepoint='0', max_codepoint='9'), min_size=1, max_size=3)
            ).map(lambda t: t[0] + t[1] + t[2])
        )
        negative = st.one_of(st.just(''), st.just('-'))

        def build_number(t):
            neg, i, f, e = t
            return neg + i + (f or '') + (e or '')

        return st.tuples(negative, int_part, frac_part, exp_part).map(build_number)

    json_number_st = st.deferred(lambda: st.builds(lambda s: s, json_number()))

    # Forward declarations for recursive structures
    # Use st.recursive to keep recursion bounded

    # value = STRING | NUMBER | obj | arr | true | false | null
    # We'll define obj and arr inside the recursive strategy

    # pair = STRING ':' value
    @st.composite
    def pair(draw, value_st):
        key = draw(json_string_st)
        val = draw(value_st)
        return f"{key}:{val}"

    def json_obj(value_st):
        # obj = '{' pair (',' pair)* '}' | '{}'
        # generate 0..5 pairs
        pairs = st.lists(pair(value_st), max_size=5)
        return pairs.map(lambda ps: "{" + ",".join(ps) + "}" if ps else "{}")

    def json_arr(value_st):
        # arr = '[' value (',' value)* ']' | '[]'
        values = st.lists(value_st, max_size=5)
        return values.map(lambda vs: "[" + ",".join(vs) + "]" if vs else "[]")

    # Recursive value strategy
    def value_strategy():
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_true,
            json_false,
            json_null,
        )
        return st.recursive(
            base,
            lambda children: st.one_of(
                json_obj(children),
                json_arr(children),
            ),
            max_leaves=10,
        )

    value_st = value_strategy()

    # The top-level json = value EOF
    json_st = value_st

    result = draw(json_st)
    return result.encode("utf-8")