from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives as strings
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and " \)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \uXXXX
        hex_digit = st.characters('0123456789abcdefABCDEF')
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))

        # Either a safe char, or an escape sequence
        char = st.one_of(
            safe_char.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Build string content with length bounded to keep size small
        content = st.lists(char, min_size=0, max_size=20).map(''.join)
        return content.map(lambda s: f'"{s}"')

    # NUMBER strategy: produce valid JSON numbers as strings
    def json_number():
        # Use Hypothesis floats and convert to JSON number strings
        # Limit floats to finite numbers, no inf or nan
        # Also include integers
        # We'll generate strings directly to avoid float formatting issues
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        frac_part = st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)
            .map(lambda f: f"{f:.6f}".lstrip("0"))
        )
        # Exponent part
        exp_part = st.one_of(
            st.just(""),
            st.integers(min_value=-10, max_value=10).map(lambda e: f"e{e}")
        )

        # Compose number string carefully
        def compose_number():
            sign = st.one_of(st.just(""), st.just("-"))
            int_str = int_part
            frac_str = st.one_of(
                st.just(""),
                st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)
                .map(lambda f: f"{f:.6f}".lstrip("0"))
            )
            exp_str = exp_part
            # Instead of floats, simpler to build number strings directly:
            # sign + int + optional frac + optional exp
            # We'll do this with a composite strategy below
            return st.tuples(sign, int_part, st.one_of(st.just(""), st.text(min_size=1, max_size=7).filter(lambda s: s.startswith('.'))), exp_part).map(
                lambda t: t[0] + t[1] + t[2] + t[3]
            )

        # But the above is complicated; simpler to use Hypothesis built-in numbers and convert to JSON strings:
        # Use floats and ints separately
        int_strat = st.integers(min_value=-(10**6), max_value=10**6).map(str)
        float_strat = st.floats(min_value=-(10**6), max_value=10**6, allow_nan=False, allow_infinity=False).map(
            lambda f: format(f, '.6g')
        )
        return st.one_of(int_strat, float_strat)

    # Forward declaration for recursive strategy
    # We'll build value recursively with bounded depth and size
    def json_value():
        # Base cases: string, number, true, false, null
        base = st.one_of(
            json_string(),
            json_number(),
            json_true,
            json_false,
            json_null,
        )

        # Recursive cases: object and array
        # Use st.recursive to keep size bounded
        def extend(value_strat):
            # pair: STRING ':' value
            pair = st.tuples(json_string(), value_strat).map(lambda t: f"{t[0]}:{t[1]}")

            # object: '{' pair (',' pair)* '}' or '{}'
            obj = st.one_of(
                st.lists(pair, min_size=1, max_size=3).map(lambda pairs: "{" + ",".join(pairs) + "}"),
                st.just("{}")
            )

            # array: '[' value (',' value)* ']' or '[]'
            arr = st.one_of(
                st.lists(value_strat, min_size=1, max_size=3).map(lambda vals: "[" + ",".join(vals) + "]"),
                st.just("[]")
            )

            return st.one_of(obj, arr)

        return st.recursive(base, extend, max_leaves=10)

    # Draw the full JSON value string
    json_str = draw(json_value())

    # Return as bytes (UTF-8)
    return json_str.encode("utf-8")