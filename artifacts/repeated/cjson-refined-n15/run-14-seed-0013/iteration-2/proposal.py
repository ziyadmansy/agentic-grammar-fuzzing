from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, "g"))
    # JSON numbers can also be integers, so include ints as well
    json_int = st.integers().map(str)
    json_number = st.one_of(json_int, json_number)

    # JSON strings: must produce valid JSON string literals
    # We'll generate unicode strings and then encode them as JSON strings
    # Use repr-like escaping for safety, but Hypothesis has a built-in json string strategy
    # However, to keep control, we build our own:
    def json_string_escape(s: str) -> str:
        # Escape backslash, quotes, control chars, and non-printables
        def esc_char(c):
            o = ord(c)
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
            elif o < 0x20:
                return '\\u%04x' % o
            else:
                return c
        return '"' + ''.join(esc_char(c) for c in s) + '"'

    json_string = st.text(
        alphabet=st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=20,
    ).map(json_string_escape)

    # Forward declaration for recursive structures
    # We'll use st.recursive to build arrays and objects

    # Placeholder for value strategy
    # We define a function to build it recursively
    def json_value():
        # Base cases: string, number, true, false, null
        base = st.one_of(
            json_string,
            json_number,
            json_true,
            json_false,
            json_null,
        )
        # Recursive cases: array and object
        # Use recursive to keep size bounded
        return st.recursive(
            base,
            lambda children: st.one_of(
                # array: [ value (, value)* ] or []
                st.lists(children, min_size=0, max_size=5).map(
                    lambda vs: "[" + ",".join(vs) + "]"
                ),
                # object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=st.text(
                        alphabet=st.characters(
                            blacklist_characters=['"', '\\'],
                            min_codepoint=0x20,
                            max_codepoint=0x10FFFF,
                        ),
                        min_size=1,
                        max_size=10,
                    ).map(json_string_escape),
                    values=children,
                    min_size=0,
                    max_size=5,
                ).map(
                    lambda d: "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"
                ),
            ),
            max_leaves=10,
        )

    # Compose the full JSON text with EOF
    json_text = json_value().map(lambda s: s)

    s = draw(json_text)
    return s.encode("utf-8")