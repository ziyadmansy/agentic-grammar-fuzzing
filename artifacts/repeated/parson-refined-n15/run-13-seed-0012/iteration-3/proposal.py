from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives as strings
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with safe codepoints only
    # SAFECODEPOINT excludes control chars and backslash, quote
    # We'll generate Python strings and then json-encode them to ensure correctness
    # but since we can't import json, we manually escape quotes and backslash here.
    def json_string():
        # Generate unicode strings excluding surrogates and control chars
        # Use characters from U+0020 (space) to U+10FFFF excluding surrogates
        # We'll filter out surrogates explicitly
        def safe_char():
            return st.characters(
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
                blacklist_categories=('Cs',),  # Surrogates
                blacklist_characters=['\\', '"']
            )
        # Generate strings of length 0 to 20
        s = st.text(safe_char(), min_size=0, max_size=20)
        # Escape backslash and quote manually
        def escape_json_string(s):
            s = s.replace('\\', '\\\\').replace('"', '\\"')
            # Also escape control characters if any slipped in (shouldn't)
            # but we excluded control chars, so no need.
            return f'"{s}"'
        return s.map(escape_json_string)

    json_string_st = json_string()

    # NUMBER strategy: generate JSON numbers as strings
    # Use Hypothesis floats and ints, then convert to JSON number strings
    def json_number():
        # Generate floats and ints, then convert to JSON number string
        # Limit floats to finite values, no NaN or inf
        # Use decimals with limited precision to avoid long strings
        # We'll generate from floats and ints separately and combine
        int_str = st.integers(min_value=-10**6, max_value=10**6).map(str)
        float_str = st.floats(
            min_value=-1e6,
            max_value=1e6,
            allow_infinity=False,
            allow_nan=False,
            width=32,
        ).map(lambda f: format(f, '.6g'))
        return st.one_of(int_str, float_str)

    json_number_st = json_number()

    # Recursive JSON value strategy
    # We'll build from primitives and recurse into arrays and objects
    # Limit max depth to 3 to keep sizes bounded

    # Forward declaration for recursion
    json_value = st.deferred()

    # Array: '[' value (, value)* ']'
    json_array = st.lists(json_value, min_size=0, max_size=5).map(
        lambda vs: "[" + ",".join(vs) + "]"
    )

    # Object: '{' pair (, pair)* '}' or '{}'
    # pair: STRING ':' value
    json_pair = st.tuples(json_string_st, json_value).map(
        lambda p: f"{p[0]}:{p[1]}"
    )
    json_object = st.lists(json_pair, min_size=0, max_size=5).map(
        lambda ps: "{" + ",".join(ps) + "}"
    )

    # Define json_value now
    json_value_strategy = st.recursive(
        st.one_of(
            json_string_st,
            json_number_st,
            json_null,
            json_true,
            json_false,
        ),
        lambda children: st.one_of(
            json_array,
            json_object,
        ),
        max_leaves=20,
    )

    # Draw a JSON string from the strategy
    s = draw(json_value_strategy)
    # Encode as UTF-8 bytes
    return s.encode("utf-8")