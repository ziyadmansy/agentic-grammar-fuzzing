from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_bool = st.one_of(json_true, json_false)
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, '.15g'))
    # JSON string respecting the grammar: no control chars, no unescaped quotes or backslashes
    # We'll generate unicode strings and then escape them properly.
    def escape_json_string(s: str) -> str:
        # Escape backslash, quote, and control chars
        def esc_char(c):
            if c == '"':
                return '\\"'
            elif c == '\\':
                return '\\\\'
            elif c == '\b':
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
        return '"' + ''.join(esc_char(c) for c in s) + '"'
    json_string = st.text(
        alphabet=st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',),  # control chars
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=20,
    ).map(escape_json_string)

    # Recursive JSON values: string, number, obj, arr, true, false, null
    # We'll use st.recursive to keep size bounded.
    # Define base values first
    base = st.one_of(json_string, json_number, json_bool, json_null)

    # Forward declarations for obj and arr
    # obj: '{' pair (',' pair)* '}' | '{}'
    # pair: STRING ':' value
    # arr: '[' value (',' value)* ']' | '[]'

    # We'll define pair and obj/arr inside the recursive function

    def json_value():
        # We define a recursive strategy for JSON values
        # base values + obj + arr
        # Use st.recursive to limit depth and size
        def pairs():
            # pair: STRING ':' value
            # STRING is json_string, value is json_value()
            return st.tuples(json_string, json_value()).map(lambda p: p[0] + ':' + p[1])

        def obj():
            # empty object or object with pairs separated by commas
            return st.one_of(
                st.just('{}'),
                st.lists(pairs(), min_size=1, max_size=5).map(lambda ps: '{' + ','.join(ps) + '}')
            )

        def arr():
            # empty array or array with values separated by commas
            return st.one_of(
                st.just('[]'),
                st.lists(json_value(), min_size=1, max_size=5).map(lambda vs: '[' + ','.join(vs) + ']')
            )

        # Compose recursive strategy
        return st.recursive(
            base,
            lambda children: st.one_of(obj(), arr()),
            max_leaves=10,
        )

    # Draw the top-level JSON value and append EOF (nothing)
    result = draw(json_value())
    return result.encode('utf-8')