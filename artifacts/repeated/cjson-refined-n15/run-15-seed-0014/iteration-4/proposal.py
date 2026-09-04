from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string, roughly matching the grammar (no control chars, escapes simplified)
    # We allow some escapes to keep near-valid cases
    def json_string():
        # Characters allowed inside strings: safe codepoints or escapes
        # We'll generate unicode strings and then escape them properly
        # To keep it simple, generate strings without control chars and backslash/quote
        safe_chars = st.text(
            alphabet=(
                # exclude control chars, backslash, quote
                st.characters(
                    blacklist_characters=['\\', '"'],
                    min_codepoint=0x20,
                    max_codepoint=0x10FFFF,
                )
            ),
            min_size=0,
            max_size=20,
        )
        # We allow some escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        # To keep it simple, generate safe strings and randomly insert escapes
        # We'll just generate safe strings here for simplicity
        s = draw(safe_chars)
        # Escape backslashes and quotes (should not be present, but just in case)
        s_escaped = s.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{s_escaped}"'

    json_string_st = st.builds(lambda s: s, json_string())

    # JSON number: generate numbers as strings matching grammar
    # We'll generate floats and ints and format them accordingly
    def json_number():
        # Generate int or float or scientific notation
        # To keep near-valid, generate floats with optional exponent
        sign = st.sampled_from(["", "-"])
        int_part = st.one_of(st.just("0"), st.integers(min_value=1, max_value=10**6).map(str))
        frac_part = st.one_of(st.just(""), st.floats(min_value=0, max_value=1).map(lambda f: f"{f:.6f}".lstrip("0")))
        # frac_part will be like ".123456" or ""
        # exponent part
        exp_part = st.one_of(
            st.just(""),
            st.tuples(
                st.sampled_from(["e", "E"]),
                st.sampled_from(["", "+", "-"]),
                st.integers(min_value=0, max_value=1000),
            ).map(lambda t: f"{t[0]}{t[1]}{t[2]}")
        )
        # Compose number string
        def compose(sign_, int_, frac_, exp_):
            # frac_ might be like ".123456" or ""
            # frac_ from floats might have leading zero, fix that
            if frac_ and not frac_.startswith("."):
                frac_ = "." + frac_.lstrip("0").lstrip(".")
                if frac_ == ".":
                    frac_ = ""
            return f"{sign_}{int_}{frac_}{exp_}"
        return st.builds(compose, sign, int_part, frac_part, exp_part)

    json_number_st = json_number()

    # Recursive JSON value
    # We'll limit max depth to keep sizes bounded
    max_depth = 4

    def json_value_strategy(depth=0):
        if depth >= max_depth:
            # At max depth, only primitives
            return st.one_of(json_string_st, json_number_st, json_null, json_true, json_false)
        else:
            # Compose object, array, or primitives
            obj_st = st.dictionaries(
                keys=json_string_st,
                values=json_value_strategy(depth + 1),
                min_size=0,
                max_size=5,
            ).map(lambda d: "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}")

            arr_st = st.lists(
                json_value_strategy(depth + 1),
                min_size=0,
                max_size=5,
            ).map(lambda l: "[" + ",".join(l) + "]")

            return st.one_of(
                json_string_st,
                json_number_st,
                obj_st,
                arr_st,
                json_null,
                json_true,
                json_false,
            )

    # Generate full JSON text and encode as bytes
    json_text = draw(json_value_strategy())
    # Append EOF (not needed in output, but grammar expects EOF)
    # Return bytes
    return json_text.encode("utf-8")