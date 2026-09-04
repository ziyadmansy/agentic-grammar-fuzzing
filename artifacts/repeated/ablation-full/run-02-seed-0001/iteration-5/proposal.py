from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # STRING: roughly safe JSON strings with escapes
    # We'll generate unicode strings and escape them properly
    def json_string():
        # Use a subset of unicode excluding control chars and quotes/backslash
        # We'll generate Python strings and then JSON-encode them
        # Hypothesis has st.text with min_codepoint and max_codepoint
        # We'll exclude control chars (<= 0x1F), quotes, backslash
        def escape_json_string(s: str) -> str:
            # Escape backslash and quotes and control chars
            # Also escape other special chars with \uXXXX
            result = []
            for c in s:
                o = ord(c)
                if c == '"':
                    result.append('\\"')
                elif c == '\\':
                    result.append('\\\\')
                elif c == '\b':
                    result.append('\\b')
                elif c == '\f':
                    result.append('\\f')
                elif c == '\n':
                    result.append('\\n')
                elif c == '\r':
                    result.append('\\r')
                elif c == '\t':
                    result.append('\\t')
                elif o <= 0x1F:
                    result.append(f'\\u{o:04x}')
                else:
                    result.append(c)
            return '"' + ''.join(result) + '"'

        return st.text(
            alphabet=(
                # All unicode except control chars, quotes, backslash
                # We'll filter out quotes and backslash in a filter
                # and control chars by min_codepoint
                # min_codepoint=0x20 to exclude control chars
                # max_codepoint=0x10FFFF
                # We'll filter out '"' and '\\' after generation
            ),
            min_size=0,
            max_size=20,
        ).filter(lambda s: '"' not in s and '\\' not in s).map(escape_json_string)

    json_string_st = json_string()

    # Forward declaration for recursive structures
    # We'll use st.recursive to build obj and arr

    # pair: STRING ':' value
    # We'll generate pairs as (string, value) and format them as '"key":value'

    # We'll define a function to generate values recursively
    # To keep sizes bounded, max_leaves=10 or so

    def json_value():
        # Base values
        base = st.one_of(
            json_string_st,
            json_number,
            json_true,
            json_false,
            json_null,
        )
        # Recursive structures: obj and arr
        # obj: '{' pair (',' pair)* '}' or '{}'
        # arr: '[' value (',' value)* ']' or '[]'

        # pair: STRING ':' value
        def json_pair():
            return st.tuples(json_string_st, json_value()).map(
                lambda kv: f"{kv[0]}:{kv[1]}"
            )

        # obj
        json_obj = st.lists(json_pair(), max_size=5).map(
            lambda pairs: "{" + ",".join(pairs) + "}" if pairs else "{}"
        )
        # arr
        json_arr = st.lists(json_value(), max_size=5).map(
            lambda values: "[" + ",".join(values) + "]" if values else "[]"
        )

        return st.recursive(
            base,
            lambda children: st.one_of(json_obj, json_arr),
            max_leaves=10,
        )

    # Generate the full json value and append EOF (nothing)
    json_full = json_value()

    s = draw(json_full)
    return s.encode("utf-8")