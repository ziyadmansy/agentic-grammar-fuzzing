from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # JSON string strategy
    # SAFECODEPOINT: any Unicode codepoint except control chars and " or \
    # We'll use st.text with blacklist_chars to approximate
    # Escape sequences are handled by escaping " and \ and control chars
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars, " and \)
        # We'll generate text and then escape it properly
        # To keep near-valid, allow some escapes
        # Use st.text with min_size=0, max_size=20 for bounded length
        s = draw(st.text(
            alphabet=st.characters(
                blacklist_characters=['"', '\\'] + [chr(c) for c in range(0x00, 0x20)],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            ),
            min_size=0,
            max_size=20,
        ))
        # Escape backslashes and quotes
        s = s.replace('\\', '\\\\').replace('"', '\\"')
        # Also escape control characters if any slipped in (shouldn't)
        # But to be safe, replace control chars with escapes
        def escape_char(c):
            if c == '\b':
                return '\\b'
            elif c == '\f':
                return '\\f'
            elif c == '\n':
                return '\\n'
            elif c == '\r':
                return '\\r'
            elif c == '\t':
                return '\\t'
            elif ord(c) < 0x20:
                return '\\u%04x' % ord(c)
            else:
                return c
        s = ''.join(escape_char(c) for c in s)
        return f'"{s}"'

    # JSON number strategy
    number = st.builds(
        lambda neg, int_part, frac, exp: (
            ('-' if neg else '') +
            int_part +
            ('.' + frac if frac else '') +
            (exp if exp else '')
        ),
        neg=st.booleans(),
        int_part=st.one_of(
            st.just('0'),
            st.text(st.characters(min_codepoint=ord('1'), max_codepoint=ord('9')), min_size=1, max_size=1).flatmap(
                lambda first: st.tuples(st.just(first), st.text(st.characters(min_codepoint=ord('0'), max_codepoint=ord('9')), max_size=10))
            ).map(lambda t: t[0] + t[1])
        ),
        frac=st.one_of(st.none(), st.text(st.characters(min_codepoint=ord('0'), max_codepoint=ord('9')), min_size=1, max_size=5)),
        exp=st.one_of(
            st.none(),
            st.builds(
                lambda e, s, d: e + s + d,
                e=st.sampled_from(['e', 'E']),
                s=st.sampled_from(['+', '-', '']),
                d=st.text(st.characters(min_codepoint=ord('0'), max_codepoint=ord('9')), min_size=1, max_size=3),
            )
        )
    )

    # JSON literals
    literals = st.sampled_from(['true', 'false', 'null'])

    # Recursive JSON value strategy
    # We'll define a helper function to build the recursive strategy

    # Forward declaration for value
    # We'll use st.deferred to allow recursion
    def json_value():
        return st.deferred(lambda: value_strategy)

    # Pair: STRING ':' value
    @st.composite
    def pair(draw):
        k = draw(json_string())
        v = draw(json_value())
        return f'{k}:{v}'

    # Object: '{' pair (',' pair)* '}' or '{}'
    @st.composite
    def obj(draw):
        pairs = draw(st.lists(pair(), max_size=3))
        if pairs:
            return '{' + ','.join(pairs) + '}'
        else:
            return '{}'

    # Array: '[' value (',' value)* ']' or '[]'
    @st.composite
    def arr(draw):
        values = draw(st.lists(json_value(), max_size=3))
        if values:
            return '[' + ','.join(values) + ']'
        else:
            return '[]'

    # Compose the recursive value strategy
    value_strategy = st.recursive(
        base=st.one_of(
            st.builds(json_string),
            number,
            literals,
        ),
        extend=lambda children: st.one_of(
            obj(),
            arr(),
        ),
        max_leaves=10,
    )

    # Draw a value and append EOF (nothing)
    val = draw(value_strategy)
    # Return bytes
    return val.encode('utf-8')