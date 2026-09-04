from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy matching grammar: '"' (ESC | SAFECODEPOINT)* '"'
    # SAFECODEPOINT: any char except " \ and control chars (U+0000-U+001F)
    # ESC: \ followed by one of ["\/bfnrt] or \uXXXX
    # We'll generate strings with safe unicode codepoints and some escapes

    # Characters allowed inside strings (excluding " and \ and control chars)
    safe_chars = st.characters(
        blacklist_characters=['"', '\\'],
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    )

    # Escape sequences
    simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
    # Unicode escape: \uXXXX where X is hex digit
    hex_digit = st.sampled_from('0123456789abcdefABCDEF')
    unicode_escape = st.builds(
        lambda a,b,c,d: '\\u' + a + b + c + d,
        hex_digit, hex_digit, hex_digit, hex_digit
    )
    escape_seq = st.one_of(simple_escapes, unicode_escape)

    # Compose string content: mix safe chars and escape sequences
    # To keep near-valid, allow some escapes, but mostly safe chars
    string_content = st.lists(
        st.one_of(
            safe_chars,
            escape_seq.map(lambda s: s),  # keep escapes as is
        ),
        min_size=0,
        max_size=20,
    ).map(lambda chars: ''.join(chars))

    json_string = string_content.map(lambda s: f'"{s}"')

    # NUMBER: '-'? INT ('.' [0-9]+)? EXP?
    # We'll generate numbers as strings using floats and ints, then convert to string
    def number_str():
        # Generate int or float or scientific notation as string
        # Use floats and ints from hypothesis and format accordingly
        # To keep near-valid, sometimes produce invalid numbers (e.g. leading zeros)
        def gen_number():
            # 80% valid, 20% near-valid (e.g. leading zeros)
            valid = draw(st.booleans())
            if valid:
                # valid number
                n = draw(st.one_of(st.integers(min_value=-100000, max_value=100000),
                                   st.floats(allow_infinity=False, allow_nan=False, width=32)))
                # Format number as JSON number string
                if isinstance(n, int):
                    return str(n)
                else:
                    # Format float with minimal representation
                    s = format(n, '.15g')
                    # Ensure no trailing dot
                    if s.endswith('.'):
                        s += '0'
                    return s
            else:
                # near-valid number: e.g. leading zeros, trailing dot, missing digits after dot
                parts = []
                if draw(st.booleans()):
                    parts.append('-')
                # leading zeros
                leading_zeros = draw(st.integers(min_value=0, max_value=3))
                parts.append('0' * leading_zeros)
                # digits
                digits = draw(st.text(min_size=1, max_size=5, alphabet='0123456789'))
                parts.append(digits)
                # optional dot with optional digits
                if draw(st.booleans()):
                    parts.append('.')
                    if draw(st.booleans()):
                        parts.append(draw(st.text(min_size=0, max_size=3, alphabet='0123456789')))
                # optional exponent
                if draw(st.booleans()):
                    parts.append(draw(st.sampled_from(['e', 'E'])))
                    if draw(st.booleans()):
                        parts.append(draw(st.sampled_from(['+', '-'])))
                    parts.append(draw(st.text(min_size=1, max_size=3, alphabet='0123456789')))
                return ''.join(parts)

        return gen_number()

    json_number = st.deferred(lambda: st.builds(number_str))

    # Forward declaration for recursive structures
    # We'll define value recursively with bounded depth

    # Define value strategy recursively
    def json_value():
        # Compose value strategy with recursion
        # Use st.recursive with base cases: string, number, true, false, null
        base = st.one_of(
            json_string,
            json_number,
            json_true,
            json_false,
            json_null,
        )

        # Recursive containers: obj and arr
        # obj: '{' pair (',' pair)* '}' or '{}'
        # pair: STRING ':' value
        # arr: '[' value (',' value)* ']' or '[]'

        # pair strategy
        def pair():
            return st.tuples(json_string, value).map(lambda p: f"{p[0]}:{p[1]}")

        # obj strategy
        def obj():
            # empty or with pairs
            pairs = st.lists(pair(), max_size=5)
            return pairs.map(lambda ps: '{' + (','.join(ps) if ps else '') + '}')

        # arr strategy
        def arr():
            values = st.lists(value, max_size=5)
            return values.map(lambda vs: '[' + (','.join(vs) if vs else '') + ']')

        containers = st.one_of(obj(), arr())

        return st.recursive(base, lambda children: containers, max_leaves=10)

    value = json_value()

    # Compose full json: value EOF
    # We just return value as bytes
    s = draw(value)
    return s.encode('utf-8')