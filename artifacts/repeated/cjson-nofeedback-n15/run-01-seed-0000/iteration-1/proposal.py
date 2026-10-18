from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then json-encode them to ensure correctness.
    # But since we cannot import json or eval, we build strings manually.
    # We'll generate unicode strings excluding control chars and quotes/backslash,
    # then escape as needed.
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars, quote, backslash)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Compose a string of length 0 to 20
        base_str = st.text(safe_chars, min_size=0, max_size=20)

        # Escape some characters randomly
        def escape_json_string(s: str) -> str:
            # Escape backslash and quote, and control chars if any (should not be present)
            res = []
            for c in s:
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
                else:
                    # For safety, if control char, encode as \uXXXX
                    if ord(c) < 0x20:
                        res.append('\\u%04x' % ord(c))
                    else:
                        res.append(c)
            return '"' + ''.join(res) + '"'

        s = draw(base_str)
        return escape_json_string(s)

    json_string_st = st.deferred(json_string)

    # NUMBER strategy: generate valid JSON numbers as strings
    # Use hypothesis floats converted to JSON number strings with bounded size
    def json_number():
        # Generate floats and ints as strings
        # Limit exponent range and decimal digits to keep size bounded
        # Also include integers
        int_str = st.integers(min_value=-10**6, max_value=10**6).map(str)
        float_str = st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ).map(lambda f: format(f, '.6g'))  # up to 6 significant digits

        return st.one_of(int_str, float_str)

    json_number_st = st.deferred(json_number)

    # Recursive value strategy
    # Use st.recursive to build nested arrays and objects with bounded depth and size
    base = st.one_of(
        json_string_st,
        json_number_st,
        json_null,
        json_true,
        json_false,
    )

    # Pair: STRING ':' value
    @st.composite
    def pair(draw):
        k = draw(json_string_st)
        v = draw(value)
        return f"{k}:{v}"

    # Forward declaration for value to allow recursion
    @st.composite
    def value(draw):
        # Compose recursive structures with limited depth and size
        # Use st.recursive with base and extend with arrays and objects
        # We'll define arrays and objects here to avoid circular import issues

        # Arrays: '[' value (',' value)* ']' or '[]'
        @st.composite
        def arr(draw):
            # Generate list of values, max length 5 to keep size bounded
            elements = draw(st.lists(value, max_size=5))
            if elements:
                return "[" + ",".join(elements) + "]"
            else:
                return "[]"

        # Objects: '{' pair (',' pair)* '}' or '{}'
        @st.composite
        def obj(draw):
            # Generate list of pairs, max length 5
            pairs = draw(st.lists(pair, max_size=5))
            if pairs:
                return "{" + ",".join(pairs) + "}"
            else:
                return "{}"

        # Compose recursive strategy
        # We limit recursion by controlling max_size in lists and using st.recursive
        # But since we are inside a composite, we do manual recursion control by depth param
        # To keep it simple, we use st.recursive outside this function

        # We will use st.recursive outside, so here just pick base or recursive
        # But to avoid infinite recursion, we limit depth by a parameter
        # We'll implement a helper with depth parameter

        # We cannot pass depth param easily here, so instead we define value as st.recursive outside

        # This function is only used inside st.recursive, so just return base or recursive

        # We'll just return base here, actual recursion is handled outside
        return draw(base)

    # Now define value with recursion using st.recursive
    # Recursive step adds arrays and objects
    value = st.recursive(
        base,
        lambda children: st.one_of(
            # arrays of children
            st.lists(children, max_size=5).map(lambda vs: "[" + ",".join(vs) + "]"),
            # objects with pairs: keys are strings, values are children
            st.lists(
                st.tuples(json_string_st, children),
                max_size=5,
            ).map(lambda pairs: "{" + ",".join(f"{k}:{v}" for k, v in pairs) + "}"),
        ),
        max_leaves=20,
    )

    # Compose full JSON: value + EOF
    json_text = draw(value)
    return json_text.encode("utf-8")