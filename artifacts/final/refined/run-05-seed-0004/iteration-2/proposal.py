from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes
    # Use st.text with safe codepoints and escape manually
    def json_string():
        # safe codepoints excluding control chars and quotes/backslash
        safe_chars = (
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # Compose string with length limit to keep size bounded
        s = st.text(safe_chars, min_size=0, max_size=20)

        # Escape backslash and quotes, and control chars if any
        def escape_json_string(t):
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
                    # Unicode escape for control chars
                    return '\\u%04x' % ord(c)
                else:
                    return c
            return '"' + ''.join(esc_char(c) for c in t) + '"'

        return s.map(escape_json_string)

    json_string_st = json_string()

    # NUMBER strategy: use Hypothesis built-in floats converted to JSON number strings
    # but restrict to finite numbers and reasonable size
    def json_number():
        # Use decimal strings to avoid float formatting quirks
        # Generate integers or floats with limited digits
        int_part = st.integers(min_value=-10**6, max_value=10**6)
        frac_part = st.one_of(st.just(""), st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False).map(lambda f: str(f)[1:] if '.' in str(f) else ""))
        exp_part = st.one_of(st.just(""), st.integers(min_value=-10, max_value=10).map(lambda e: "e%d" % e))
        # Compose number string
        def compose_number(i, f, e):
            # f is either "" or something like ".123"
            # But floats() may produce "0.123" so fix that
            if f == "":
                frac = ""
            else:
                # f is string like "0.123" or "0.0", take substring from decimal point
                if '.' in f:
                    frac = f[f.index('.'):]
                else:
                    frac = ""
            return str(i) + frac + e

        return st.tuples(int_part, frac_part, exp_part).map(lambda t: compose_number(*t))

    json_number_st = json_number()

    # Recursive JSON value strategy
    # Use st.recursive with base cases and recursive cases

    base = st.one_of(
        json_string_st,
        json_number_st,
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: arrays and objects
    # Arrays: [ value (, value)* ]
    # Objects: { pair (, pair)* }
    # pair: STRING : value

    # We'll define value recursively as string strategy that produces JSON text fragments

    # To avoid infinite recursion and huge outputs, limit max depth and max size

    def json_value():
        return st.deferred(lambda: value_st)

    # pair strategy: "string" : value
    def json_pair():
        return st.tuples(json_string_st, json_value()).map(lambda t: t[0] + ":" + t[1])

    # array strategy: [ value (, value)* ]
    def json_array():
        # limit size to max 5 elements
        return st.lists(json_value(), min_size=0, max_size=5).map(
            lambda vs: "[" + ",".join(vs) + "]"
        )

    # object strategy: { pair (, pair)* }
    def json_object():
        # limit size to max 5 pairs
        return st.lists(json_pair(), min_size=0, max_size=5).map(
            lambda ps: "{" + ",".join(ps) + "}"
        )

    # Compose recursive strategy
    value_st = st.recursive(
        base,
        lambda children: st.one_of(json_array(), json_object()),
        max_leaves=10,
    )

    # Draw a JSON string and encode as UTF-8 bytes
    s = draw(value_st)
    return s.encode("utf-8")