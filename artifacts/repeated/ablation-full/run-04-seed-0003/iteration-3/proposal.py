from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly matching grammar, with escapes and safe codepoints
    # We'll generate Python strings and then JSON-encode them with minimal escaping
    # but to keep control, we generate strings with safe codepoints and some escapes.
    # Use a small subset of escapes to keep near-valid cases.
    def json_string():
        # Characters allowed inside strings (excluding control chars and quotes/backslash)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Some escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Mix safe chars and escapes
        # To keep it simple, generate a list of either safe chars or escapes
        chunk = st.one_of(
            safe_chars.map(lambda c: c),
            escapes.map(lambda e: e),
        )
        # Generate a list of chunks, length bounded
        chunks = st.lists(chunk, min_size=0, max_size=20)
        def assemble(chunks):
            # Join all chunks into a string, escapes are already escaped
            # safe chars are single chars
            s = "".join(chunks)
            return f'"{s}"'
        return chunks.map(assemble)

    json_string_st = json_string()

    # NUMBER: generate numbers matching grammar roughly
    # Use floats and ints, then convert to string
    def json_number():
        # Generate int or float or exponent form as string
        # To keep near-valid, generate strings matching the grammar
        # Use floats with optional exponent
        # We'll generate numbers as strings directly
        def number_str():
            sign = st.one_of(st.just(""), st.just("-"))
            int_part = st.one_of(st.just("0"), st.integers(min_value=1, max_value=10**6).map(str))
            frac_part = st.one_of(st.just(""), st.floats(min_value=0, max_value=1).map(lambda f: f"{f:.6f}".lstrip("0")))
            # frac_part above produces strings like ".123456"
            # But to keep control, generate fractional digits explicitly
            frac_digits = st.one_of(st.just(""), st.text(min_size=1, max_size=6, alphabet="0123456789").map(lambda d: "." + d))
            exp_part = st.one_of(
                st.just(""),
                st.tuples(
                    st.sampled_from(["e", "E"]),
                    st.sampled_from(["", "+", "-"]),
                    st.integers(min_value=0, max_value=99).map(str),
                ).map(lambda t: t[0] + t[1] + t[2])
            )
            return st.tuples(sign, int_part, frac_digits, exp_part).map(lambda parts: "".join(parts))
        return number_str()

    json_number_st = json_number()

    # Forward declare value strategy for recursion
    # We'll use st.recursive to build nested objects and arrays

    # Pair: STRING ':' value
    @st.composite
    def json_pair(draw, value_st):
        key = draw(json_string_st)
        val = draw(value_st)
        return f"{key}:{val}"

    # Object: '{' pair (',' pair)* '}' or '{}'
    def json_object(value_st):
        # Generate 0 to 5 pairs
        pairs = st.lists(json_pair(value_st), max_size=5)
        def assemble(pairs):
            if not pairs:
                return "{}"
            return "{" + ",".join(pairs) + "}"
        return pairs.map(assemble)

    # Array: '[' value (',' value)* ']' or '[]'
    def json_array(value_st):
        values = st.lists(value_st, max_size=5)
        def assemble(values):
            if not values:
                return "[]"
            return "[" + ",".join(values) + "]"
        return values.map(assemble)

    # Recursive value strategy
    def json_value():
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_null,
            json_true,
            json_false,
        )
        # Use recursive to add obj and arr
        return st.recursive(
            base,
            lambda children: st.one_of(
                json_object(children),
                json_array(children),
            ),
            max_leaves=10,
        )

    value_st = json_value()

    # Compose full JSON: value + EOF (just value here)
    json_text = value_st

    result = draw(json_text)
    return result.encode("utf-8")