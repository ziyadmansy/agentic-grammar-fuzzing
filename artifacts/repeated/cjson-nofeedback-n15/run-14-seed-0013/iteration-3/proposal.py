from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escaped characters
        escape_chars = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape sequences
        def unicode_escape():
            hex_digit = st.characters("0123456789abcdefABCDEF")
            return st.tuples(hex_digit, hex_digit, hex_digit, hex_digit).map(
                lambda t: '\\u' + ''.join(t)
            )
        # Mix safe chars and escapes
        string_char = st.one_of(
            safe_char.map(lambda c: c),
            escape_chars,
            unicode_escape()
        )
        # Limit length to keep output size bounded
        content = string_char.flatmap(
            lambda first: st.lists(string_char, max_size=10).map(lambda rest: first + ''.join(rest))
        )
        # Or simpler: just build a string of safe chars and escapes up to length 10
        content = st.lists(string_char, max_size=10).map(''.join)
        return content.map(lambda s: '"' + s + '"')

    json_string_st = json_string()

    # NUMBER strategy: generate valid JSON numbers as strings
    def json_number():
        # Use Hypothesis floats but convert to JSON number string format
        # Limit range to avoid scientific notation with huge exponents
        # Use decimal.Decimal to format nicely
        import decimal
        def to_json_number(f):
            # Convert float to string without trailing .0 if integer
            d = decimal.Decimal(str(f))
            # Normalize to remove trailing zeros
            d = d.normalize()
            # Use plain string representation
            s = format(d, 'f')
            # If exponent needed, fallback to str(f)
            if 'E' in s or 'e' in s:
                s = str(f)
            return s
        return st.floats(
            allow_nan=False, allow_infinity=False,
            min_value=-1e10, max_value=1e10
        ).map(to_json_number)

    json_number_st = json_number()

    # Recursive JSON value strategy
    # Use st.recursive to build nested objects and arrays with bounded depth and size
    base = st.one_of(
        json_string_st,
        json_number_st,
        json_null,
        json_true,
        json_false,
    )

    # Pair: STRING : value
    def pair():
        return st.tuples(json_string_st, value).map(lambda t: f"{t[0]}:{t[1]}")

    # Forward declaration for value to use in recursive
    # We'll define value after pair and arr and obj

    # We define value here as a placeholder to allow recursion
    # We'll define it after obj and arr are defined

    # obj: '{' pair (',' pair)* '}' | '{}'
    def json_obj():
        # Empty object
        empty = st.just("{}")
        # Non-empty object: 1 to 3 pairs
        pairs = st.lists(pair(), min_size=1, max_size=3)
        non_empty = pairs.map(lambda ps: "{" + ",".join(ps) + "}")
        return st.one_of(empty, non_empty)

    # arr: '[' value (',' value)* ']' | '[]'
    def json_arr():
        # Empty array
        empty = st.just("[]")
        # Non-empty array: 1 to 3 values
        values = st.lists(value, min_size=1, max_size=3)
        non_empty = values.map(lambda vs: "[" + ",".join(vs) + "]")
        return st.one_of(empty, non_empty)

    # Now define value using st.recursive to include obj and arr
    # We need to define value as a recursive strategy that includes base and obj/arr

    # We'll define value as a recursive strategy here:
    # base is primitives
    # recursive expands to obj and arr

    # To avoid circular reference, define value as a variable first
    # Then assign it with st.recursive

    # We need pair() to use value, so we redefine pair as a function that uses value
    # We'll define pair after value is assigned

    # So we do a two-step approach:

    # 1) define base
    # 2) define value as recursive(base, expand with obj and arr)
    # 3) redefine pair using value
    # 4) redefine obj and arr using pair and value

    # Step 1: base defined above

    # Step 2: define value recursive
    # We'll define value as a placeholder first
    value = None

    # Define value recursively
    def json_value():
        # base primitives
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_null,
            json_true,
            json_false,
        )
        # recursive expansion
        def expand_children(children):
            # children is a strategy for value
            # define pair using children
            def pair():
                return st.tuples(json_string_st, children).map(lambda t: f"{t[0]}:{t[1]}")

            # obj: empty or 1-3 pairs
            empty_obj = st.just("{}")
            non_empty_obj = st.lists(pair(), min_size=1, max_size=3).map(lambda ps: "{" + ",".join(ps) + "}")
            obj = st.one_of(empty_obj, non_empty_obj)

            # arr: empty or 1-3 values
            empty_arr = st.just("[]")
            non_empty_arr = st.lists(children, min_size=1, max_size=3).map(lambda vs: "[" + ",".join(vs) + "]")
            arr = st.one_of(empty_arr, non_empty_arr)

            return st.one_of(base, obj, arr)

        return st.recursive(base, expand_children, max_leaves=10)

    value = json_value()

    # The top-level JSON is value + EOF, so just value as string
    # Return bytes encoded UTF-8
    return draw(value).encode("utf-8")