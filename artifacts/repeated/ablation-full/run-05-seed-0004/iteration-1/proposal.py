from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then json.dumps them to ensure correctness.
    # But since we can't import json or eval, we approximate by generating strings with safe chars and escapes.
    # To keep it simple, generate strings with safe unicode codepoints excluding control chars and quotes/backslash.
    # Also include some escapes.
    def json_string():
        # safe chars: exclude control chars, quote, backslash
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # We'll generate strings of length 0 to 20
        # To include escapes, we can randomly insert escape sequences
        # but to keep it simple, just generate safe chars and occasionally insert an escape sequence.
        # We'll generate a list of either safe char or escape sequence.
        escape_sequences = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Compose a list of length 0 to 20 of either safe char or escape sequence
        pieces = st.lists(
            st.one_of(
                safe_chars.map(lambda c: c),
                escape_sequences,
            ),
            min_size=0,
            max_size=20,
        )
        def to_json_string(pieces):
            # Join pieces and wrap in quotes
            return '"' + ''.join(pieces) + '"'
        return pieces.map(to_json_string)

    json_string_st = json_string()

    # NUMBER: generate numbers as strings matching the grammar
    # We'll generate floats and ints and format them accordingly
    def json_number():
        # Generate a float or int, then format as JSON number string
        # Limit magnitude and decimal places to keep size bounded
        # Use floats with limited exponent range
        def format_number(n):
            # Format number to JSON number string without trailing .0 if int
            if isinstance(n, int):
                return str(n)
            else:
                # Use repr to get a compact representation
                s = repr(n)
                # Remove trailing zeros in fractional part if any
                if '.' in s:
                    s = s.rstrip('0').rstrip('.')
                return s
        # Generate int or float
        number_st = st.one_of(
            st.integers(min_value=-10**6, max_value=10**6),
            st.floats(
                min_value=-1e6,
                max_value=1e6,
                allow_nan=False,
                allow_infinity=False,
                width=32,
            ),
        )
        return number_st.map(format_number)

    json_number_st = json_number()

    # Forward declaration for recursive value
    # We'll define value_st recursively below

    # Define obj and arr recursively using st.recursive

    # pair: STRING ':' value
    @st.composite
    def json_pair(draw, value_st):
        k = draw(json_string_st)
        v = draw(value_st)
        return f"{k}:{v}"

    # obj: '{' pair (',' pair)* '}' | '{}'
    def json_object(value_st):
        # pairs: list of 0 to 5 pairs
        pairs_st = st.lists(json_pair(value_st), max_size=5)
        def to_obj(pairs):
            if not pairs:
                return "{}"
            else:
                return "{" + ",".join(pairs) + "}"
        return pairs_st.map(to_obj)

    # arr: '[' value (',' value)* ']' | '[]'
    def json_array(value_st):
        values_st = st.lists(value_st, max_size=5)
        def to_arr(values):
            if not values:
                return "[]"
            else:
                return "[" + ",".join(values) + "]"
        return values_st.map(to_arr)

    # Now define value recursively
    def value_strategy():
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_null,
            json_true,
            json_false,
        )
        # recursive container
        return st.recursive(
            base,
            lambda children: st.one_of(
                json_object(children),
                json_array(children),
            ),
            max_leaves=10,
        )

    value_st = value_strategy()

    # The top-level json is value + EOF (implicit)
    result = draw(value_st)
    return result.encode("utf-8")