from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode them as JSON strings.
    # To keep it simple, use st.text with safe ranges and then json.dumps to encode.
    # But since we cannot import json, we manually produce strings with escapes for quotes and backslashes.
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        # We'll allow a subset of Unicode excluding control chars and quotes/backslash
        safe_chars = (
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # Compose string with some escapes
        base_str = st.text(safe_chars, min_size=0, max_size=10)

        # Insert some escapes randomly
        def escape_json(s: str) -> str:
            # Escape backslash and quote
            s = s.replace('\\', '\\\\').replace('"', '\\"')
            # Replace control chars with escapes if any (should be none due to safe_chars)
            # But just in case, replace \b, \f, \n, \r, \t
            s = s.replace('\b', '\\b').replace('\f', '\\f').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
            return s

        s = draw(base_str)
        escaped = escape_json(s)
        return f'"{escaped}"'

    json_string_st = st.deferred(json_string)

    # NUMBER strategy: produce valid JSON numbers as strings
    # Use the grammar: '-'? INT ('.' [0-9]+)? EXP?
    # We'll build strings directly.
    def json_number():
        sign = st.one_of(st.just(''), st.just('-'))
        int_part = st.one_of(st.just('0'), st.integers(min_value=1, max_value=10**6).map(str))
        frac_part = st.one_of(st.just(''), st.tuples(st.just('.'), st.text(st.digits, min_size=1, max_size=6)).map(lambda t: t[0] + t[1]))
        exp_part = st.one_of(
            st.just(''),
            st.tuples(
                st.sampled_from(['e', 'E']),
                st.sampled_from(['+', '-', '']),
                st.text(st.digits, min_size=1, max_size=4)
            ).map(lambda t: t[0] + t[1] + t[2])
        )
        return st.tuples(sign, int_part, frac_part, exp_part).map(lambda parts: ''.join(parts))

    json_number_st = st.deferred(json_number)

    # Forward declarations for recursive structures
    # We'll define value recursively with bounded depth
    def json_value():
        # Use recursive to bound depth
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_true,
            json_false,
            json_null,
        )

        # Recursive containers: obj and arr
        def json_obj():
            # pair: STRING ':' value
            pair = st.tuples(json_string_st, json_value()).map(lambda t: f"{t[0]}:{t[1]}")
            # obj: '{' pair (',' pair)* '}' | '{}'
            # To keep size bounded, limit number of pairs
            pairs = st.lists(pair, max_size=3)
            return pairs.map(lambda ps: '{' + ','.join(ps) + '}' if ps else '{}')

        def json_arr():
            # arr: '[' value (',' value)* ']' | '[]'
            values = st.lists(json_value(), max_size=3)
            return values.map(lambda vs: '[' + ','.join(vs) + ']' if vs else '[]')

        return st.recursive(
            base,
            lambda children: st.one_of(json_obj(), json_arr()),
            max_leaves=10,
        )

    val_st = json_value()

    # Compose full json: value EOF
    json_full = val_st.map(lambda s: s.encode('utf-8'))

    return draw(json_full)