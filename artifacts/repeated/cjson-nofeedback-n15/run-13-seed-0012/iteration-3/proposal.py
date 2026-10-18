from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then JSON-encode them
    # but since we can't import json, we build strings carefully.
    # We'll generate strings with safe unicode codepoints excluding control chars and quotes/backslash.
    # To keep it simple, generate ASCII printable except control and backslash and quote.
    safe_char = st.characters(
        blacklist_characters=['"', '\\'],
        min_codepoint=0x20,
        max_codepoint=0x7E,
    )
    # Also allow some escapes by inserting backslash sequences sometimes
    # We'll do a small helper to generate strings with some escapes
    def json_string():
        # Generate a string with length 0..20
        s = draw(st.text(safe_char, max_size=20))
        # Randomly insert some escapes
        # We'll replace some chars with escapes
        import random
        escapes = ['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t']
        s_list = list(s)
        for i in range(len(s_list)):
            if draw(st.booleans()) and len(s_list) > 0:
                # Replace char with an escape sequence
                s_list[i] = draw(st.sampled_from(escapes))
        # Join carefully: escapes are two chars, so flatten list
        # But we replaced single chars with strings, so flatten:
        result = "".join(s_list)
        return f'"{result}"'

    json_string_st = st.deferred(lambda: st.builds(json_string))

    # NUMBER strategy: generate valid JSON numbers as strings
    # Use Hypothesis float or decimal and format as JSON number string
    def json_number():
        # Generate float or int as string
        # We'll generate int or float strings matching grammar
        # Use floats with limited exponent range
        sign = draw(st.sampled_from(["", "-"]))
        int_part = draw(st.one_of(st.just("0"), st.from_regex(r"[1-9][0-9]*", fullmatch=True)))
        frac_part = draw(st.one_of(st.just(""), st.from_regex(r"\.[0-9]+", fullmatch=True)))
        exp_part = draw(st.one_of(st.just(""), st.from_regex(r"[Ee][+-]?[0-9]+", fullmatch=True)))
        return f"{sign}{int_part}{frac_part}{exp_part}"

    json_number_st = st.deferred(lambda: st.builds(json_number))

    # Recursive value strategy
    # We'll use st.recursive to build nested objects and arrays with bounded depth
    # Base cases: string, number, true, false, null
    base = st.one_of(
        json_string_st,
        json_number_st,
        json_true,
        json_false,
        json_null,
    )

    # Forward declare obj and arr to use in value
    # obj: '{' pair (',' pair)* '}' | '{}'
    # pair: STRING ':' value
    # arr: '[' value (',' value)* ']' | '[]'

    # pair strategy: STRING ':' value
    @st.composite
    def pair(draw):
        key = draw(json_string_st)
        val = draw(value)
        return f"{key}:{val}"

    # obj strategy
    @st.composite
    def obj(draw):
        # empty or with pairs
        empty = draw(st.booleans())
        if empty:
            return "{}"
        else:
            # up to 5 pairs
            pairs = draw(st.lists(pair(), max_size=5))
            return "{" + ",".join(pairs) + "}"

    # arr strategy
    @st.composite
    def arr(draw):
        empty = draw(st.booleans())
        if empty:
            return "[]"
        else:
            # up to 5 values
            vals = draw(st.lists(value, max_size=5))
            return "[" + ",".join(vals) + "]"

    # Now define value as recursive
    value = st.recursive(
        base,
        lambda children: st.one_of(obj(), arr()),
        max_leaves=10,
    )

    # Compose full json: value EOF
    val = draw(value)
    return val.encode("utf-8")