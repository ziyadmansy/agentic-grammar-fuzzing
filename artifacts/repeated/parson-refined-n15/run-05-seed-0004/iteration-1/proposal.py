from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode them as JSON strings.
    # To keep it simple, use st.text with safe characters and escape quotes/backslashes.
    def json_string():
        # safe codepoints exclude control chars and quotes/backslash
        safe_chars = (
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # Compose a string with safe chars and some escapes
        base = st.text(safe_chars, min_size=0, max_size=20)

        # We will randomly insert some escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        # For simplicity, generate a string and then replace some chars with escapes
        def escape_json_string(s: str) -> str:
            import random

            escapes = {
                '"': r'\"',
                '\\': r'\\',
                '\b': r'\b',
                '\f': r'\f',
                '\n': r'\n',
                '\r': r'\r',
                '\t': r'\t',
            }
            # Replace some chars with escapes randomly
            chars = list(s)
            for i in range(len(chars)):
                c = chars[i]
                if c in escapes and random.random() < 0.3:
                    chars[i] = escapes[c]
                elif ord(c) < 0x20 and random.random() < 0.3:
                    # replace control chars with \uXXXX
                    chars[i] = "\\u%04x" % ord(c)
            return "".join(chars)

        s = draw(base)
        s = escape_json_string(s)
        return '"' + s + '"'

    json_string_st = st.builds(json_string)

    # NUMBER strategy: generate numbers as strings matching the grammar
    # Use floats and ints, then convert to string with JSON-compatible formatting
    def json_number():
        # Generate floats or ints within reasonable range
        # Use floats with limited decimal places and optional exponent
        # Also generate ints including zero and negatives
        def number_to_json(n):
            # Format number to JSON number string
            # Use repr for floats to keep exponent if any
            if isinstance(n, int):
                return str(n)
            else:
                # Format float with minimal digits, allow exponent
                s = repr(n)
                # Remove trailing .0 if present for floats that are ints
                if s.endswith(".0"):
                    s = s[:-2]
                return s

        # Draw int or float
        is_float = draw(st.booleans())
        if is_float:
            # floats in range -1e6 to 1e6, with some chance of exponent
            base = draw(st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False))
            return number_to_json(base)
        else:
            base = draw(st.integers(min_value=-1_000_000, max_value=1_000_000))
            return number_to_json(base)

    json_number_st = st.builds(json_number)

    # Recursive JSON value strategy
    # Use st.recursive with base cases: string, number, true, false, null
    # Recursive cases: object and array

    # Forward declaration for value
    # We'll define value_st inside this function to capture recursion

    # Pair: STRING ':' value
    @st.composite
    def pair(draw):
        k = draw(json_string_st)
        v = draw(value_st)
        return f"{k}:{v}"

    # Object: '{' pair (',' pair)* '}' or '{}'
    @st.composite
    def obj(draw):
        # Choose number of pairs 0 to 3 to keep size bounded
        n = draw(st.integers(min_value=0, max_value=3))
        if n == 0:
            return "{}"
        pairs = [draw(pair) for _ in range(n)]
        return "{" + ",".join(pairs) + "}"

    # Array: '[' value (',' value)* ']' or '[]'
    @st.composite
    def arr(draw):
        n = draw(st.integers(min_value=0, max_value=3))
        if n == 0:
            return "[]"
        values = [draw(value_st) for _ in range(n)]
        return "[" + ",".join(values) + "]"

    # Now define value_st recursively
    base_values = st.one_of(
        json_string_st,
        json_number_st,
        json_true,
        json_false,
        json_null,
    )

    # We define value_st here so pair, obj, arr can reference it
    # Use st.deferred to allow recursion
    value_st = st.deferred(lambda: st.one_of(
        base_values,
        obj(),
        arr(),
    ))

    # Draw the top-level json value and append EOF (nothing)
    val = draw(value_st)
    # Return as bytes
    return val.encode("utf-8")