from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then json-encode them to ensure correctness.
    # But since we cannot import json or use eval, we approximate:
    # We'll generate strings with safe unicode codepoints excluding control chars and quotes/backslash.
    # We'll also add some escapes.
    def json_string():
        # safe codepoints excluding control chars, quote, backslash
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # We add some escapes manually with some probability
        escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Compose string parts: mostly safe chars, sometimes escapes
        part = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
        )
        # Compose a string of length 0 to 20 parts
        parts = st.lists(part, max_size=20)
        def to_json_string(parts):
            s = ''.join(parts)
            return '"' + s + '"'
        return parts.map(to_json_string)

    json_string_st = json_string()

    # NUMBER: use the grammar for numbers
    # We'll generate numbers as strings matching the grammar
    def json_number():
        # sign
        sign = st.one_of(st.just(''), st.just('-'))
        # int part
        int_part = st.one_of(
            st.just('0'),
            st.integers(min_value=1, max_value=9999999).map(str),
        )
        # frac part
        frac_part = st.one_of(st.just(''), st.floats(min_value=0, max_value=1).map(lambda f: '.' + str(f)[2:]))
        # exp part
        exp_sign = st.one_of(st.just(''), st.sampled_from(['e', 'E']))
        exp_sign2 = st.one_of(st.just(''), st.sampled_from(['+', '-']))
        exp_digits = st.one_of(st.just(''), st.integers(min_value=0, max_value=999).map(str))
        def combine_exp(e, s, d):
            if e == '' or d == '':
                return ''
            return e + s + d
        exp_part = st.tuples(exp_sign, exp_sign2, exp_digits).map(lambda t: combine_exp(*t))
        return st.tuples(sign, int_part, frac_part, exp_part).map(lambda t: ''.join(t))

    json_number_st = json_number()

    # Recursive value
    # We'll use st.recursive to build obj and arr with bounded depth

    # Forward declare value strategy
    # We'll define value as a recursive strategy below

    # pair: STRING ':' value
    @st.composite
    def pair(draw, value_st):
        k = draw(json_string_st)
        v = draw(value_st)
        return k + ':' + v

    # obj: '{' pair (',' pair)* '}' or '{}'
    def obj_strategy(value_st):
        # pairs list
        pairs = st.lists(pair(value_st), max_size=5)
        return st.one_of(
            st.just('{}'),
            pairs.map(lambda ps: '{' + ','.join(ps) + '}')
        )

    # arr: '[' value (',' value)* ']' or '[]'
    def arr_strategy(value_st):
        values = st.lists(value_st, max_size=5)
        return st.one_of(
            st.just('[]'),
            values.map(lambda vs: '[' + ','.join(vs) + ']')
        )

    # Now define value recursively
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
                obj_strategy(children),
                arr_strategy(children),
            ),
            max_leaves=10,
        )

    value_st = value_strategy()

    # Compose full json: value + EOF (just value here)
    s = draw(value_st)
    return s.encode('utf-8')