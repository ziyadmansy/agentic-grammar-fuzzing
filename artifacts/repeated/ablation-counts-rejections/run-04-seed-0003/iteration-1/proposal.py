from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode as JSON strings with escapes.
    # To keep it simple, use st.text with safe characters and escape quotes/backslashes.
    def json_string():
        # safe codepoints excluding control chars and quotes/backslash
        safe_chars = (
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # Compose string with length limit to keep size bounded
        s = draw(st.text(safe_chars, min_size=0, max_size=20))
        # Escape backslash and quote
        s_escaped = s.replace('\\', '\\\\').replace('"', '\\"')
        # Add some escapes randomly
        # We'll randomly insert some simple escapes
        import random
        escapes = ['\\b', '\\f', '\\n', '\\r', '\\t', '\\"', '\\\\']
        # Insert up to 2 random escapes at random positions
        s_list = list(s_escaped)
        for _ in range(draw(st.integers(min_value=0, max_value=2))):
            if not s_list:
                break
            pos = draw(st.integers(min_value=0, max_value=len(s_list)-1))
            esc = draw(st.sampled_from(escapes))
            s_list.insert(pos, esc)
        final_str = ''.join(s_list)
        return f'"{final_str}"'

    json_string_st = st.deferred(lambda: st.just(json_string()))

    # NUMBER: generate numbers as strings matching the grammar
    def json_number():
        # Use floats and ints, then convert to string with JSON number format
        # Limit magnitude and digits to keep size bounded
        sign = draw(st.sampled_from(['', '-']))
        int_part = draw(st.one_of(st.just('0'), st.integers(min_value=1, max_value=999999).map(str)))
        frac_part = draw(st.one_of(st.just(''), st.floats(min_value=0, max_value=1).map(lambda f: f'{f:.6f}'.lstrip('0'))))
        # frac_part might be like '.123456' or ''
        if frac_part and not frac_part.startswith('.'):
            frac_part = '.' + frac_part
        exp_part = draw(st.one_of(st.just(''), st.integers(min_value=-10, max_value=10).map(lambda e: f'e{e}')))
        return f"{sign}{int_part}{frac_part}{exp_part}"

    json_number_st = st.deferred(lambda: st.just(json_number()))

    # Recursive JSON values
    # We'll define a recursive strategy with bounded depth and size
    def json_value():
        # Compose base values
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_null,
            json_true,
            json_false,
        )
        # Recursive containers
        # Use st.recursive to build arrays and objects
        def container_children(children):
            # pair: STRING ':' value
            pair = st.tuples(json_string_st, children).map(lambda p: f"{p[0]}:{p[1]}")
            obj = st.one_of(
                st.just('{}'),
                st.lists(pair, min_size=1, max_size=3).map(lambda pairs: '{' + ','.join(pairs) + '}'),
            )
            arr = st.one_of(
                st.just('[]'),
                st.lists(children, min_size=1, max_size=3).map(lambda vs: '[' + ','.join(vs) + ']'),
            )
            return st.one_of(obj, arr)

        return st.recursive(base, container_children, max_leaves=10)

    val = draw(json_value())
    return val.encode('utf-8')