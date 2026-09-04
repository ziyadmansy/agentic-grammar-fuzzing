from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and " \)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \uXXXX
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.builds(
            lambda a,b,c,d: '\\u' + a + b + c + d,
            hex_digit, hex_digit, hex_digit, hex_digit
        )
        # Either safe char or escape sequence
        char = st.one_of(
            safe_char.map(lambda c: c),
            escapes,
            unicode_escape
        )
        # Build string with length 0..20 to keep size bounded
        return st.builds(
            lambda chars: '"' + ''.join(chars) + '"',
            st.lists(char, max_size=20)
        )

    # NUMBER strategy: match grammar for NUMBER
    def json_number():
        # INT fragment
        int_part = st.one_of(
            st.just("0"),
            st.builds(lambda d, ds: d + ''.join(ds),
                      st.characters(min_codepoint=49, max_codepoint=57),  # '1'..'9'
                      st.lists(st.characters(min_codepoint=48, max_codepoint=57), max_size=5))
        )
        # Fractional part
        frac_part = st.one_of(
            st.just(""),
            st.builds(lambda digits: "." + digits,
                      st.text(st.characters(min_codepoint=48, max_codepoint=57), min_size=1, max_size=5))
        )
        # Exponent part
        exp_sign = st.one_of(st.just(""), st.sampled_from(["+", "-"]))
        exp_part = st.one_of(
            st.just(""),
            st.builds(lambda e, s, d: e + s + d,
                      st.sampled_from(["e", "E"]),
                      exp_sign,
                      st.text(st.characters(min_codepoint=48, max_codepoint=57), min_size=1, max_size=3))
        )
        # Optional minus sign
        sign = st.one_of(st.just(""), st.just("-"))
        return st.builds(lambda s, i, f, e: s + i + f + e, sign, int_part, frac_part, exp_part)

    # Forward declaration for recursive value
    # We'll use st.recursive to build obj and arr

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string(),
        json_number(),
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: obj and arr
    # To keep size bounded, limit max depth and max elements

    # Pair: STRING ':' value
    @st.composite
    def pair(draw, value_strat):
        key = draw(json_string())
        val = draw(value_strat)
        return f"{key}:{val}"

    def json_obj(value_strat):
        # Either empty object or object with 1..3 pairs
        pairs = st.lists(pair(value_strat), max_size=3)
        return st.one_of(
            st.just("{}"),
            pairs.map(lambda ps: "{" + ",".join(ps) + "}")
        )

    def json_arr(value_strat):
        # Either empty array or array with 1..5 values
        arr_vals = st.lists(value_strat, max_size=5)
        return st.one_of(
            st.just("[]"),
            arr_vals.map(lambda vs: "[" + ",".join(vs) + "]")
        )

    # Recursive value strategy
    value = st.recursive(
        base_values,
        lambda children: st.one_of(
            json_obj(children),
            json_arr(children)
        ),
        max_leaves=10,
    )

    # Compose full JSON with EOF (just ensure full consumption)
    json_text = value

    s = draw(json_text)
    return s.encode("utf-8")