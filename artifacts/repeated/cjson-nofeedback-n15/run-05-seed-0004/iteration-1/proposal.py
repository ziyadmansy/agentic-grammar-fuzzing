from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_bool = st.one_of(json_true, json_false)
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, "g"))
    # JSON string with safe codepoints and escapes
    # We reuse the grammar: STRING : '"' (ESC | SAFECODEPOINT)* '"'
    # SAFECODEPOINT excludes control chars and " and \
    # We'll generate strings and then escape them properly.
    def json_string():
        # Generate unicode strings excluding control chars and " and \
        # We'll generate strings of length up to 20 to keep size bounded
        def escape_char(c):
            # Escape backslash and quote and control chars
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
                # Use unicode escape for other control chars
                return '\\u%04x' % ord(c)
            else:
                return c

        # Generate a string of length 0 to 20 with codepoints excluding " and \ and control chars
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        s = draw(st.text(safe_chars, max_size=20))
        escaped = "".join(escape_char(c) for c in s)
        return f'"{escaped}"'

    json_string_st = st.deferred(json_string)

    # Recursive JSON values: string, number, object, array, true, false, null
    # Use st.recursive to keep size bounded
    def json_value():
        base = st.one_of(
            json_string_st,
            json_number,
            json_bool,
            json_null,
        )
        # Recursive containers: obj and arr
        # obj: '{' pair (',' pair)* '}' | '{}'
        # pair: STRING ':' value
        # arr: '[' value (',' value)* ']' | '[]'

        # pair strategy: (string, value)
        def pair():
            k = json_string_st
            v = st.deferred(json_value)
            return st.tuples(k, v).map(lambda kv: f"{kv[0]}:{kv[1]}")

        obj = st.lists(pair(), max_size=5).map(
            lambda pairs: "{" + ",".join(pairs) + "}" if pairs else "{}"
        )
        arr = st.lists(st.deferred(json_value), max_size=5).map(
            lambda vs: "[" + ",".join(vs) + "]" if vs else "[]"
        )
        return st.one_of(base, obj, arr)

    val = draw(json_value())
    # The top-level json is value EOF, so just val
    return val.encode("utf-8")