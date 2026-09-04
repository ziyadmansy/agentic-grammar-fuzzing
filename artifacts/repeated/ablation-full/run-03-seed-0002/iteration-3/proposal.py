from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll produce Python strings and then json.dumps them to ensure correctness,
    # but since we can't import json or exec, we build strings manually here.
    # Instead, we produce strings with safe codepoints and some escapes.
    # To keep it simple, produce strings with ASCII printable except control and quote/backslash,
    # plus some escapes.
    def json_string():
        # Characters allowed inside JSON strings (SAFECODEPOINT)
        safe_chars = (
            [chr(c) for c in range(0x20, 0x7F) if c not in (0x22, 0x5C)]  # exclude " and \
            + ['\\' + c for c in ['"', '\\', '/', 'b', 'f', 'n', 'r', 't']]
        )
        # Also allow unicode escapes \uXXXX
        # We'll add some \uXXXX escapes occasionally
        def char_or_escape():
            # 80% safe char, 20% escape
            choice = draw(st.integers(min_value=1, max_value=100))
            if choice <= 80:
                return draw(st.sampled_from(safe_chars))
            else:
                # unicode escape \uXXXX
                hex4 = ''.join(draw(st.sampled_from('0123456789abcdef')) for _ in range(4))
                return '\\u' + hex4

        length = draw(st.integers(min_value=0, max_value=20))
        chars = [char_or_escape() for _ in range(length)]
        s = ''.join(chars)
        return '"' + s + '"'

    json_string_st = st.deferred(json_string)

    # NUMBER strategy: produce valid JSON numbers as strings
    def json_number():
        # Compose number parts
        sign = draw(st.sampled_from(['', '-']))
        int_part = draw(st.one_of(
            st.just('0'),
            st.integers(min_value=1, max_value=10**6).map(str)
        ))
        frac_part = draw(st.one_of(
            st.just(''),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False).map(
                lambda f: '.' + str(f).split('.')[1] if '.' in str(f) else ''
            )
        ))
        exp_part = draw(st.one_of(
            st.just(''),
            st.integers(min_value=-100, max_value=100).map(lambda e: 'e' + str(e))
        ))
        # Clean frac_part to ensure digits only after dot
        if frac_part and not frac_part[1:].isdigit():
            frac_part = ''
        num = sign + int_part + frac_part + exp_part
        return num

    json_number_st = st.deferred(json_number)

    # Recursive JSON value strategy
    def json_value():
        # Use recursive to build nested objects and arrays
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_true,
            json_false,
            json_null,
        )
        # Recursive containers
        def obj():
            # pair: STRING ':' value
            # We'll produce pairs as '"key":value'
            # keys are strings without escapes for simplicity
            key = draw(st.text(
                alphabet=(
                    [chr(c) for c in range(0x20, 0x7F) if c not in (0x22, 0x5C)]
                ),
                min_size=1,
                max_size=10
            ))
            # Escape quotes and backslashes in key
            key_esc = key.replace('\\', '\\\\').replace('"', '\\"')
            key_json = '"' + key_esc + '"'
            val = draw(json_value())
            return key_json + ':' + val

        obj_st = st.lists(st.deferred(obj), max_size=5).map(
            lambda pairs: '{' + (','.join(pairs) if pairs else '') + '}'
        )

        arr_st = st.lists(json_value(), max_size=5).map(
            lambda vals: '[' + (','.join(vals) if vals else '') + ']'
        )

        return draw(st.recursive(
            base,
            lambda children: st.one_of(obj_st, arr_st),
            max_leaves=10
        ))

    # Compose full JSON text with EOF
    json_text = json_value()
    # Return bytes
    return json_text.encode('utf-8')