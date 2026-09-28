from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # JSON strings: use Hypothesis text with safe codepoints, escape quotes and backslashes
    def json_string():
        # safe codepoints excluding control chars and quotes/backslash
        safe_chars = st.text(
            alphabet=(
                st.characters(
                    blacklist_characters=['"', '\\'],
                    min_codepoint=0x20,
                    max_codepoint=0x10FFFF,
                )
            ),
            min_size=0,
            max_size=20,
        )
        # Compose string with escapes for quotes and backslash
        @st.composite
        def escaped_string(draw):
            s = draw(safe_chars)
            # randomly escape some quotes and backslashes
            def escape_char(c):
                if c == '"':
                    return r'\"'
                elif c == '\\':
                    return r'\\'
                elif ord(c) < 0x20:
                    # control chars escaped as \uXXXX
                    return '\\u%04x' % ord(c)
                else:
                    return c
            # but since safe_chars excludes quotes and backslash, no need to escape here
            # just wrap in quotes
            return '"' + s + '"'
        return escaped_string()

    json_string_strat = json_string()

    # Recursive JSON values: string, number, obj, arr, true, false, null
    # Use st.recursive to keep size bounded
    base = st.one_of(
        json_string_strat,
        json_number,
        json_null,
        json_true,
        json_false,
    )

    # Forward declarations for obj and arr to be used in recursive
    # obj: '{' pair (',' pair)* '}' | '{}'
    # pair: STRING ':' value
    # arr: '[' value (',' value)* ']' | '[]'

    # We'll define value recursively
    def json_value():
        return st.deferred(lambda: value)

    # pair: STRING ':' value
    @st.composite
    def pair(draw):
        k = draw(json_string_strat)
        v = draw(json_value())
        return k + ":" + v

    # obj: '{}' or '{' pair (',' pair)* '}'
    @st.composite
    def obj(draw):
        # decide empty or not
        empty = draw(st.booleans())
        if empty:
            return "{}"
        else:
            pairs = draw(st.lists(pair(), min_size=1, max_size=3))
            return "{" + ",".join(pairs) + "}"

    # arr: '[]' or '[' value (',' value)* ']'
    @st.composite
    def arr(draw):
        empty = draw(st.booleans())
        if empty:
            return "[]"
        else:
            values = draw(st.lists(json_value(), min_size=1, max_size=3))
            return "[" + ",".join(values) + "]"

    # Now define value as recursive
    value = st.recursive(
        base,
        lambda children: st.one_of(obj(), arr()),
        max_leaves=5,
    )

    # Compose full json: value + EOF (implicit)
    result = draw(value)
    return result.encode("utf-8")