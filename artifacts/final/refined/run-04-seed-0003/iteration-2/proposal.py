from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: quoted string with escapes and safe codepoints
    # We'll generate unicode strings excluding control chars and quotes/backslash,
    # then escape them properly.
    def json_string():
        # safe characters excluding control chars, quote, backslash
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # generate a string of length 0..20
        s = st.text(safe_chars, min_size=0, max_size=20)

        # escape function for JSON string
        def escape_json_string(u: str) -> str:
            # escape backslash and quote, and control chars as \uXXXX
            res = []
            for c in u:
                o = ord(c)
                if c == '"':
                    res.append('\\"')
                elif c == '\\':
                    res.append('\\\\')
                elif c == '\b':
                    res.append('\\b')
                elif c == '\f':
                    res.append('\\f')
                elif c == '\n':
                    res.append('\\n')
                elif c == '\r':
                    res.append('\\r')
                elif c == '\t':
                    res.append('\\t')
                elif o < 0x20:
                    res.append('\\u%04x' % o)
                else:
                    res.append(c)
            return '"' + ''.join(res) + '"'

        return s.map(escape_json_string)

    json_string_st = json_string()

    # NUMBER strategy: integers and floats with optional exponent
    json_number = st.one_of(
        # integer
        st.integers(min_value=-(10**9), max_value=10**9).map(str),
        # float with fractional part and optional exponent
        st.floats(allow_infinity=False, allow_nan=False, width=32).map(lambda f: format(f, 'g'))
    )

    # Recursive JSON value strategy
    # We'll limit max depth to keep size bounded
    def json_value():
        # base: primitives
        base = st.one_of(
            json_string_st,
            json_number,
            json_null,
            json_true,
            json_false,
        )

        # recursive container strategy
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string_st.map(lambda s: s[1:-1]),  # remove quotes for keys
                    values=children,
                    min_size=0,
                    max_size=3,
                ).map(
                    lambda d: (
                        '{' + ','.join(f'"{k}":{v}' for k, v in d.items()) + '}'
                        if d else '{}'
                    )
                ),
                # array: [ value (, value)* ] or []
                st.lists(children, min_size=0, max_size=3).map(
                    lambda l: '[' + ','.join(l) + ']' if l else '[]'
                ),
            ),
            max_leaves=10,
        )

    val = draw(json_value())
    return val.encode('utf-8')