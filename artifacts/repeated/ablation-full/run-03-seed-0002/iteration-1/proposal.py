from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then json-encode them to ensure correctness.
    # But since we cannot import json, we approximate with escapes.
    def json_string():
        # Characters allowed inside strings (excluding control chars and " \)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Include some escapes explicitly
        escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Compose string parts: either safe char or escape sequence
        string_char = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            # Unicode escape sequences \uXXXX
            st.integers(min_value=0, max_value=0xFFFF).map(lambda i: '\\u%04x' % i),
        )
        # Generate a list of 0 to 20 such chars, join and wrap in quotes
        s = draw(st.lists(string_char, max_size=20))
        return '"' + ''.join(s) + '"'

    json_string_st = st.deferred(lambda: st.builds(lambda s: s, json_string()))

    # NUMBER strategy: produce valid JSON numbers as strings
    def json_number():
        # Compose number parts according to grammar
        sign = st.one_of(st.just(''), st.just('-'))
        int_part = st.one_of(
            st.just('0'),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        frac_part = st.one_of(st.just(''), st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False).map(lambda f: '.' + str(f).split('.')[1]))
        exp_part = st.one_of(
            st.just(''),
            st.tuples(
                st.sampled_from(['e', 'E']),
                st.one_of(st.just(''), st.sampled_from(['+', '-'])),
                st.integers(min_value=0, max_value=1000)
            ).map(lambda t: t[0] + t[1] + str(t[2]))
        )
        # Compose number string
        def compose(sign_, int_, frac_, exp_):
            return sign_ + int_ + frac_ + exp_
        return st.builds(compose, sign, int_part, frac_part, exp_part)

    json_number_st = st.deferred(lambda: json_number())

    # Forward declaration for recursive structures
    # We'll define value recursively with bounded depth
    def json_value():
        # Base cases: string, number, true, false, null
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_true,
            json_false,
            json_null,
        )
        # Recursive cases: obj and arr
        # Use st.recursive to limit depth and size
        def extend(value_st):
            # pair: STRING ':' value
            pair = st.tuples(json_string_st, value_st).map(lambda p: p[0] + ':' + p[1])
            # obj: '{' pair (',' pair)* '}' or '{}'
            obj = st.one_of(
                st.just('{}'),
                st.lists(pair, min_size=1, max_size=5).map(lambda pairs: '{' + ','.join(pairs) + '}')
            )
            # arr: '[' value (',' value)* ']' or '[]'
            arr = st.one_of(
                st.just('[]'),
                st.lists(value_st, min_size=1, max_size=5).map(lambda values: '[' + ','.join(values) + ']')
            )
            return st.one_of(obj, arr)

        return st.recursive(base, extend, max_leaves=10)

    # Draw a value and encode as bytes
    val = draw(json_value())
    return val.encode('utf-8')