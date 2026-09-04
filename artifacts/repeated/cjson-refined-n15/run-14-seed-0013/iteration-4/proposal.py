from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: valid JSON strings with escapes
    # Use a small subset of safe characters and escapes to keep it simple
    # SAFECODEPOINT: any unicode codepoint except control chars and " \ 
    # We'll use st.text with a whitelist of safe chars and some escapes
    safe_chars = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789"
        " !#$%&'()*+,-./:;<=>?@[]^_`{|}~"
    )
    # Escape sequences allowed: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
    # We'll simplify by allowing only a subset of escapes for fuzzing
    def json_string():
        # Compose a string with safe chars and some escapes
        # We'll generate a list of characters or escapes and join them
        def char_or_escape():
            # 80% safe char, 20% escape
            return st.one_of(
                st.sampled_from(safe_chars),
                st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']),
                # Unicode escape \uXXXX
                st.builds(lambda h: "\\u" + h, st.text("0123456789abcdefABCDEF", min_size=4, max_size=4))
            )
        # Generate list of 0 to 20 chars or escapes
        parts = st.lists(char_or_escape(), max_size=20)
        return parts.map(lambda parts: '"' + "".join(parts) + '"')

    json_string = json_string()

    # NUMBER strategy: use Hypothesis built-in floats and ints, then convert to JSON number strings
    # We'll generate strings matching the NUMBER grammar
    def json_number():
        # Generate a float or int and convert to JSON number string
        # Use floats with finite values only
        def number_to_json(n):
            # Format number to JSON number string without trailing .0 if int
            if isinstance(n, int):
                return str(n)
            else:
                # Use repr to get a compact representation
                s = repr(n)
                # JSON requires exponent E or e, repr uses e
                # repr may produce inf/nan, filter those out
                if s in ("inf", "-inf", "nan", "-nan"):
                    return "0"
                return s
        # Generate int or float
        num = st.one_of(
            st.integers(min_value=-10**6, max_value=10**6),
            st.floats(allow_infinity=False, allow_nan=False, width=32)
        )
        return num.map(number_to_json)

    json_number = json_number()

    # Recursive value strategy
    # We'll use st.recursive with base cases: string, number, true, false, null
    # Recursive cases: object and array

    # Forward declare value strategy for recursion
    # We'll define a helper function to build the recursive strategy

    def json_value():
        base = st.one_of(json_string, json_number, json_true, json_false, json_null)

        # obj: '{' pair (',' pair)* '}' or '{}'
        # pair: STRING ':' value
        # arr: '[' value (',' value)* ']' or '[]'

        # Use @st.composite to build obj and arr with draw

        @st.composite
        def json_obj(draw):
            # Generate 0 to 5 pairs
            n = draw(st.integers(min_value=0, max_value=5))
            # Generate pairs
            # STRING keys
            keys = draw(st.lists(json_string, min_size=n, max_size=n, unique=True))
            # values: recursive values
            values = [draw(value) for _ in range(n)]
            pairs = [f"{k}:{v}" for k, v in zip(keys, values)]
            if pairs:
                s = "{" + ",".join(pairs) + "}"
            else:
                s = "{}"
            return s

        @st.composite
        def json_arr(draw):
            n = draw(st.integers(min_value=0, max_value=5))
            values = [draw(value) for _ in range(n)]
            if values:
                s = "[" + ",".join(values) + "]"
            else:
                s = "[]"
            return s

        # Recursive strategy
        return st.recursive(
            base,
            lambda children: st.one_of(json_obj(), json_arr()),
            max_leaves=10,
        )

    value = json_value()

    # Compose full JSON text: value + EOF
    json_text = value.map(lambda s: s)

    # Draw the JSON string and encode as bytes
    s = draw(json_text)
    return s.encode("utf-8")