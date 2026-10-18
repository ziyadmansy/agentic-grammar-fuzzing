from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then JSON-encode them with escapes.
    # To keep it simple, generate unicode strings excluding control chars and quotes/backslash,
    # then escape them properly.
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars, quote, backslash)
        safe_chars = (
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # Compose a string of length 0..20
        s = st.text(safe_chars, min_size=0, max_size=20)

        def encode_json_string(x: str) -> str:
            # Escape backslash, quote, and control chars as per JSON spec
            def escape_char(c):
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

            return '"' + ''.join(escape_char(ch) for ch in x) + '"'

        return s.map(encode_json_string)

    json_string_st = json_string()

    # NUMBER strategy: integers and floats with optional exponent
    # We'll generate numbers as strings matching the grammar.
    def json_number():
        # integer part
        int_part = st.one_of(
            st.just("0"),
            st.tuples(
                st.characters(min_codepoint='1', max_codepoint='9'),
                st.text(st.digits, max_size=10),
            ).map(lambda t: t[0] + t[1]),
        )
        # fraction part
        fraction = st.one_of(st.just(""), st.tuples(st.just("."), st.text(st.digits, min_size=1, max_size=10)).map(lambda t: t[0] + t[1]))
        # exponent part
        exponent = st.one_of(
            st.just(""),
            st.tuples(
                st.sampled_from(["e", "E"]),
                st.sampled_from(["+", "-", ""]),
                st.text(st.digits, min_size=1, max_size=5),
            ).map(lambda t: t[0] + t[1] + t[2]),
        )
        # optional minus sign
        sign = st.one_of(st.just(""), st.just("-"))

        return st.tuples(sign, int_part, fraction, exponent).map(lambda parts: "".join(parts))

    json_number_st = json_number()

    # Recursive value strategy
    # We'll limit recursion depth and size to keep output bounded.
    # Compose value from primitives and recursive obj/arr.

    # Forward declaration for recursive use
    def json_value():
        return st.deferred(lambda: value_st)

    # Pair: STRING ':' value
    @st.composite
    def json_pair(draw):
        key = draw(json_string_st)
        val = draw(json_value())
        return f"{key}:{val}"

    # Object: '{' pair (',' pair)* '}' or '{}'
    @st.composite
    def json_object(draw):
        # limit pairs count to keep size bounded
        pairs = draw(st.lists(json_pair(), max_size=3))
        if not pairs:
            return "{}"
        return "{" + ",".join(pairs) + "}"

    # Array: '[' value (',' value)* ']' or '[]'
    @st.composite
    def json_array(draw):
        values = draw(st.lists(json_value(), max_size=3))
        if not values:
            return "[]"
        return "[" + ",".join(values) + "]"

    # Compose value strategy with recursion bounded by max_leaves
    value_st = st.recursive(
        st.one_of(
            json_string_st,
            json_number_st,
            json_true,
            json_false,
            json_null,
        ),
        lambda children: st.one_of(
            json_object(),
            json_array(),
        ),
        max_leaves=10,
    )

    # Compose full json: value + EOF (just value here)
    result = draw(value_st)
    return result.encode("utf-8")