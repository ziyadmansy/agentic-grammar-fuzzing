from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic building blocks
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings
    # SAFECODEPOINT excludes control chars and backslash, quote
    # We'll generate unicode strings and escape them properly
    def json_string():
        # Generate unicode strings without control chars or quotes/backslash
        # We'll generate strings of length up to 20 for boundedness
        # Then escape them as JSON strings
        def escape_json_string(s: str) -> str:
            # Escape backslash, quote, and control chars
            def esc_char(c):
                if c == '"':
                    return r'\"'
                elif c == '\\':
                    return r'\\'
                elif c == '\b':
                    return r'\b'
                elif c == '\f':
                    return r'\f'
                elif c == '\n':
                    return r'\n'
                elif c == '\r':
                    return r'\r'
                elif c == '\t':
                    return r'\t'
                elif ord(c) < 0x20:
                    return '\\u%04x' % ord(c)
                else:
                    return c
            return '"' + ''.join(esc_char(c) for c in s) + '"'

        # Generate strings of unicode codepoints excluding control chars and quotes/backslash
        # We'll allow characters from U+0020 (space) to U+10FFFF except " and \
        # To keep it simple, use ascii letters, digits, space, and some punctuation except " and \
        allowed_chars = (
            [chr(i) for i in range(0x20, 0x7F) if chr(i) not in ['"', '\\']]
            + ['\u00A0', '\u00A1', '\u00A9', '\u00AE', '\u00B5', '\u00B6', '\u00BF']  # some latin1 chars
        )
        s = draw(st.text(st.sampled_from(allowed_chars), max_size=20))
        return escape_json_string(s)

    json_string_st = st.deferred(json_string)

    # NUMBER strategy: generate valid JSON numbers as strings
    # Use Hypothesis floats and convert to JSON number strings
    def json_number():
        # Generate floats and ints, convert to JSON number strings
        # Limit floats to finite values, no NaN or inf
        f = draw(st.one_of(
            st.integers(min_value=-1_000_000, max_value=1_000_000).map(str),
            st.floats(allow_nan=False, allow_infinity=False, width=32).map(lambda x: format(x, '.10g'))
        ))
        return f

    json_number_st = st.deferred(json_number)

    # Recursive value strategy
    # value = STRING | NUMBER | obj | arr | true | false | null
    # Use st.recursive to build obj and arr

    # Forward declare value strategy
    value_st = st.deferred(lambda: value)

    # pair: STRING ':' value
    pair_st = st.tuples(json_string_st, value_st).map(lambda p: p[0] + ':' + p[1])

    # obj: '{' pair (',' pair)* '}' | '{}'
    def obj_st():
        # Generate 0 to 5 pairs
        pairs = st.lists(pair_st, max_size=5)
        return pairs.map(lambda ps: '{' + (','.join(ps) if ps else '') + '}')

    obj_st = st.deferred(obj_st)

    # arr: '[' value (',' value)* ']' | '[]'
    def arr_st():
        values = st.lists(value_st, max_size=5)
        return values.map(lambda vs: '[' + (','.join(vs) if vs else '') + ']')

    arr_st = st.deferred(arr_st)

    # Compose value strategy with recursion bounded by max_leaves=10
    value = st.recursive(
        st.one_of(
            json_string_st,
            json_number_st,
            json_true,
            json_false,
            json_null,
        ),
        lambda children: st.one_of(
            obj_st,
            arr_st,
        ),
        max_leaves=10,
    )

    # Draw a value and encode as bytes
    result = draw(value)
    return result.encode('utf-8')