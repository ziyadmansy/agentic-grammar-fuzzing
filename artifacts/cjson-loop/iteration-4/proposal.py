from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly matching JSON string with escapes
    # Use Hypothesis text with safe codepoints and some escapes
    def json_string():
        # safe codepoints excluding control chars and quotes/backslash
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # simple escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # unicode escape: \uXXXX
        hex_digit = st.sampled_from("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))
        # build string parts: either safe char or escape
        part = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # generate list of parts, length bounded
        parts = st.lists(part, min_size=0, max_size=20)
        s = draw(parts)
        return '"' + ''.join(s) + '"'

    json_string_st = st.deferred(json_string)

    # NUMBER: generate numbers as strings matching grammar
    def json_number():
        # integer part
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        # fraction part
        frac_part = st.one_of(
            st.none(),
            st.text(min_size=1, max_size=6, alphabet="0123456789")
        )
        # exponent part
        exp_sign = st.one_of(st.just("+"), st.just("-"), st.just(""))
        exp_digits = st.text(min_size=1, max_size=4, alphabet="0123456789")
        exp_part = st.one_of(
            st.none(),
            st.tuples(st.just("e"), exp_sign, exp_digits).map(lambda t: ''.join(t)),
            st.tuples(st.just("E"), exp_sign, exp_digits).map(lambda t: ''.join(t)),
        )
        def build_number(int_, frac, exp):
            s = int_
            if frac is not None:
                s += "." + frac
            if exp is not None:
                s += exp
            return s
        return st.builds(build_number, int_part, frac_part, exp_part)

    json_number_st = st.deferred(json_number)

    # Recursive JSON value
    # Use recursive to keep size bounded and diverse
    def json_value():
        return st.recursive(
            st.one_of(
                json_string_st,
                json_number_st,
                json_true,
                json_false,
                json_null,
            ),
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string_st.map(lambda s: s),
                    values=children,
                    min_size=0,
                    max_size=5,
                ).map(lambda d: "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"),
                # array: [ value (, value)* ] or []
                st.lists(children, min_size=0, max_size=5).map(
                    lambda l: "[" + ",".join(l) + "]"
                ),
            ),
            max_leaves=10,
        )

    val = draw(json_value())
    return val.encode("utf-8")