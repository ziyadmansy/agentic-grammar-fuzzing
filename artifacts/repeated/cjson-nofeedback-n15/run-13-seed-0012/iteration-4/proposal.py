from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \uXXXX
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))

        # Either safe char or escape sequence
        char = st.one_of(
            safe_char.map(lambda c: c),
            escapes,
            unicode_escape
        )
        # Build string content with length 0 to 20
        content = st.text(char, min_size=0, max_size=20)
        return content.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # NUMBER strategy: use Hypothesis built-in floats converted to JSON number strings
    # but restrict to finite numbers and format accordingly
    def json_number():
        # Generate floats that can be represented as JSON numbers
        # Use decimals to avoid scientific notation in some cases
        # But allow scientific notation as well
        # We'll generate strings matching the NUMBER fragment
        # Use floats between -1e6 and 1e6, finite only
        import math
        def float_to_json_number(f):
            # Format float to JSON number string
            # Use repr to get a precise representation
            s = repr(f)
            # repr can produce 'inf', 'nan' - reject those
            if s in ('inf', '-inf', 'nan'):
                return None
            # Remove trailing .0 if integer
            if '.' in s or 'e' in s or 'E' in s:
                return s
            else:
                return s
        floats = st.floats(min_value=-1e6, max_value=1e6, allow_infinity=False, allow_nan=False)
        return floats.map(float_to_json_number).filter(lambda x: x is not None)

    json_number_st = json_number()

    # Forward declaration for recursive value
    # We'll build value recursively with bounded depth

    def json_value():
        # Compose the recursive strategy
        # Base cases: string, number, true, false, null
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_true,
            json_false,
            json_null,
        )

        # Recursive cases: object and array
        # Use st.recursive to keep size bounded
        def extend(value_st):
            # pair: STRING ':' value
            pair = st.tuples(json_string_st, value_st).map(lambda t: f"{t[0]}:{t[1]}")

            # object: '{' pair (',' pair)* '}' or '{}'
            obj = st.one_of(
                st.lists(pair, max_size=5).map(lambda pairs: "{" + ",".join(pairs) + "}"),
                st.just("{}")
            )

            # array: '[' value (',' value)* ']' or '[]'
            arr = st.one_of(
                st.lists(value_st, max_size=5).map(lambda values: "[" + ",".join(values) + "]"),
                st.just("[]")
            )

            return st.one_of(obj, arr)

        return st.recursive(base, extend, max_leaves=10)

    json_st = json_value()

    s = draw(json_st)
    return s.encode("utf-8")