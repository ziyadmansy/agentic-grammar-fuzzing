from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: valid JSON strings with escapes and safe codepoints
    # We generate Python strings and then json.dumps them to ensure correctness,
    # but since we can't import json or eval, we build strings carefully.
    # We'll generate strings with safe codepoints and some escapes.
    # To keep it simple, generate unicode strings excluding control chars and quotes/backslash,
    # plus some escapes.
    # We'll produce the string content without quotes, then add quotes and escapes.

    # Characters allowed inside JSON strings (SAFECODEPOINT + ESC)
    # SAFECODEPOINT: ~["\\\u0000-\u001F]
    # We'll generate characters from 0x20 (space) to 0x10FFFF excluding " and \.
    # Also include some escapes like \n, \t, \\, \", etc.

    # Define safe characters excluding " and \ and control chars
    safe_chars = st.characters(
        blacklist_characters=['"', '\\'],
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    )

    # Escape sequences to include
    escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])

    # We build a string by mixing safe_chars and escapes
    def json_string_content():
        # Generate a list of length 0..20 of either safe char or escape sequence
        pieces = st.lists(
            st.one_of(
                safe_chars.map(lambda c: c),
                escapes,
            ),
            max_size=20,
        )
        return pieces.map(lambda chars: ''.join(chars))

    # Compose STRING strategy
    json_string = json_string_content().map(lambda s: f'"{s}"')

    # NUMBER strategy: use Hypothesis's built-in floats and ints, then format as JSON number
    # We'll generate numbers as strings matching the grammar
    def json_number():
        # Generate int part
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str),
        )
        # Optional fractional part
        frac_part = st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)
            .map(lambda f: f"{f:.10f}".lstrip("0") if f != 0 else ""),
        )
        # Optional exponent part
        exp_part = st.one_of(
            st.just(""),
            st.integers(min_value=-100, max_value=100).map(lambda e: f"e{e}" if e >= 0 else f"e{e}"),
        )
        # Compose number string
        def compose_number(i, f, e):
            # f may be like ".1234567890" or ""
            # We want to produce a valid JSON number string
            # frac_part from floats may have leading 0, so fix that
            frac = f
            if frac.startswith("0"):
                frac = frac[1:]
            # If frac is empty or just '.', remove it
            if frac == ".":
                frac = ""
            return i + frac + e

        return st.tuples(int_part, frac_part, exp_part).map(lambda t: compose_number(*t))

    json_number_str = json_number()

    # Now define recursive JSON value strategy
    # We'll generate strings, numbers, true, false, null, objects, arrays
    # Use st.recursive to keep recursion bounded

    # Forward declaration for value
    # We'll build value as string strategy producing JSON text (not Python objects)

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string,
        json_number_str,
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: objects and arrays
    # We'll define obj and arr strategies that produce JSON text

    # Pair: STRING ':' value
    @st.composite
    def pair(draw):
        k = draw(json_string)
        v = draw(value)
        return f"{k}:{v}"

    @st.composite
    def obj(draw):
        # Either empty object or with pairs
        pairs = draw(st.lists(pair(), max_size=5))
        if not pairs:
            return "{}"
        return "{" + ",".join(pairs) + "}"

    @st.composite
    def arr(draw):
        # Either empty array or with values
        values = draw(st.lists(value, max_size=5))
        if not values:
            return "[]"
        return "[" + ",".join(values) + "]"

    # Now define value recursively
    value = st.recursive(
        base_values,
        lambda children: st.one_of(obj(), arr()),
        max_leaves=10,
    )

    # Draw the final JSON text and encode as bytes
    json_text = draw(value)
    return json_text.encode("utf-8")