from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives as strings
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and " \)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        simple_escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape \uXXXX (hex digits)
        def unicode_escape():
            hex_digit = st.sampled_from('0123456789abcdefABCDEF')
            return st.tuples(hex_digit, hex_digit, hex_digit, hex_digit).map(
                lambda t: '\\u' + ''.join(t)
            )
        escape = st.one_of(simple_escapes, unicode_escape())

        # Mix safe chars and escapes
        char = st.one_of(safe_char.map(lambda c: c), escape)
        # Limit string length to keep output size bounded
        chars = st.lists(char, max_size=20)
        return chars.map(lambda cs: '"' + ''.join(cs) + '"')

    # NUMBER strategy: produce valid JSON numbers as strings
    def json_number():
        # Use Hypothesis floats converted to JSON number strings
        # But restrict to finite numbers, no NaN or inf
        # Use decimal notation, optionally with exponent
        # We'll build numbers manually to control format and keep valid JSON number grammar
        int_part = st.one_of(
            st.just("0"),
            st.tuples(st.sampled_from("123456789"), st.text(st.characters("0123456789"), max_size=5)).map(
                lambda t: t[0] + t[1]
            ),
        )
        frac_part = st.one_of(st.just(""), st.text(st.characters("0123456789"), min_size=1, max_size=5).map(lambda s: "." + s))
        exp_part = st.one_of(
            st.just(""),
            st.tuples(
                st.sampled_from("eE"),
                st.one_of(st.just("+"), st.just("-"), st.just("")),
                st.text(st.characters("0123456789"), min_size=1, max_size=3),
            ).map(lambda t: t[0] + t[1] + t[2]),
        )
        sign = st.one_of(st.just(""), st.just("-"))
        return st.tuples(sign, int_part, frac_part, exp_part).map(lambda t: "".join(t))

    # Recursive JSON value strategy
    # We'll use st.recursive with base cases: string, number, true, false, null
    # And recursive cases: object and array

    # Base values as strings
    base_values = st.one_of(
        json_string(),
        json_number(),
        json_true,
        json_false,
        json_null,
    )

    # Forward declarations for recursive
    # Object: { pair (, pair)* } or {}
    # Pair: STRING : value
    # Array: [ value (, value)* ] or []

    # We define value recursively below

    # Helper to produce pairs: STRING : value
    def json_pair(value_strat):
        return st.tuples(json_string(), value_strat).map(lambda t: f"{t[0]}:{t[1]}")

    def json_obj(value_strat):
        # Either empty object or object with 1-3 pairs (bounded)
        pairs = st.lists(json_pair(value_strat), max_size=3)
        return st.one_of(
            st.just("{}"),
            pairs.map(lambda ps: "{" + ",".join(ps) + "}"),
        )

    def json_arr(value_strat):
        # Either empty array or array with 1-5 values (bounded)
        values = st.lists(value_strat, max_size=5)
        return st.one_of(
            st.just("[]"),
            values.map(lambda vs: "[" + ",".join(vs) + "]"),
        )

    # Recursive strategy for JSON values as strings
    json_value = st.recursive(
        base_values,
        lambda children: st.one_of(
            json_obj(children),
            json_arr(children),
        ),
        max_leaves=10,
    )

    # Draw a JSON string and encode as bytes
    s = draw(json_value)
    return s.encode("utf-8")