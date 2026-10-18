from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode them as JSON strings
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and " \)
        # We'll allow some escapes as well
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # To include escapes, we can generate strings with some backslashes and escaped chars
        # But for simplicity and validity, generate normal strings and then json-encode them
        # Hypothesis has no builtin json string encoder, so we do it manually here:
        # We'll generate Python strings and then encode them with json.dumps-like escaping
        # But since we cannot import json, we do minimal escaping here:
        # Replace \ with \\, " with \", and control chars with escapes
        # We'll generate strings without control chars to simplify
        return st.text(
            alphabet=safe_chars,
            min_size=0,
            max_size=20,
        ).map(_json_escape_string)

    def _json_escape_string(s: str) -> str:
        # Escape backslash and quote
        s = s.replace('\\', '\\\\').replace('"', '\\"')
        # Escape control chars (U+0000 to U+001F) as \uXXXX
        def esc_char(c):
            if ord(c) < 0x20:
                return '\\u%04x' % ord(c)
            return c
        s = ''.join(esc_char(c) for c in s)
        return f'"{s}"'

    json_string_st = json_string()

    # NUMBER strategy: generate valid JSON numbers as strings
    # Use Hypothesis floats converted to JSON number strings with bounded size
    def json_number():
        # Generate floats and ints, then convert to JSON number strings
        # We'll generate strings matching the NUMBER grammar:
        # '-'? INT ('.' [0-9]+)? EXP?
        # We'll generate numbers as strings directly:
        # Use decimal.Decimal to avoid scientific notation? No imports allowed.
        # So generate components separately:
        sign = st.sampled_from(['', '-'])
        int_part = st.one_of(st.just('0'), st.text(st.characters('123456789'), min_size=1, max_size=5))
        frac_part = st.one_of(st.just(''), st.builds(lambda f: '.' + f, st.text(st.characters('0123456789'), min_size=1, max_size=5)))
        exp_part = st.one_of(st.just(''), st.builds(lambda e, s: 'e' + s + e, st.text(st.characters('0123456789'), min_size=1, max_size=3), st.sampled_from(['+', '-'])))
        return st.builds(lambda s, i, f, e: s + i + f + e, sign, int_part, frac_part, exp_part)

    json_number_st = json_number()

    # Forward declaration for recursive structures
    # We'll use st.recursive to build values

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string_st,
        json_number_st,
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: obj and arr
    # obj: '{' pair (',' pair)* '}' or '{}'
    # pair: STRING ':' value
    # arr: '[' value (',' value)* ']' or '[]'

    # We'll define pair as (string, value) -> '"key":value'

    # To keep recursion bounded, limit max depth and max size

    def json_value():
        return st.recursive(
            base_values,
            lambda children: st.one_of(
                json_object(children),
                json_array(children),
            ),
            max_leaves=10,
        )

    def json_object(value_st):
        # pairs: list of (string, value)
        # keys must be strings (json_string_st)
        # values from value_st
        # limit number of pairs to max 5
        pairs_st = st.lists(
            st.tuples(json_string_st, value_st),
            max_size=5,
            unique_by=lambda p: p[0],  # unique keys
        )
        def build_obj(pairs):
            if not pairs:
                return '{}'
            inner = ','.join(f'{k}:{v}' for k, v in pairs)
            return '{' + inner + '}'
        return pairs_st.map(build_obj)

    def json_array(value_st):
        # list of values max size 5
        arr_st = st.lists(value_st, max_size=5)
        def build_arr(values):
            if not values:
                return '[]'
            inner = ','.join(values)
            return '[' + inner + ']'
        return arr_st.map(build_arr)

    # Compose final json: value + EOF (implicit)
    result = draw(json_value())
    return result.encode('utf-8')