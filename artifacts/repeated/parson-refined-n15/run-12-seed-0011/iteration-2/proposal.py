from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We limit length to keep size bounded
    def json_string():
        # safe codepoints exclude control chars and " \ 
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # escape sequences allowed: \" \\ \/ \b \f \n \r \t and \uXXXX
        # We'll generate escapes as literals for simplicity
        escapes = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t',
        ])
        # Unicode escape \uXXXX with hex digits
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))

        # Compose either safe char or escape or unicode escape
        char_piece = st.one_of(
            safe_char.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Generate string content length 0..20 to keep size bounded
        content = st.lists(char_piece, max_size=20).map(''.join)
        return content.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # NUMBER strategy: use Hypothesis built-in floats and ints, then format as JSON number string
    # Limit magnitude and decimal places to keep size bounded
    def json_number():
        # Generate int or float as string
        # Use floats with limited exponent and decimal places
        int_part = st.integers(min_value=-10**6, max_value=10**6)
        frac_part = st.one_of(
            st.just(''),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)
            .map(lambda f: f"{f:.6f}".lstrip('0') if f != 0 else '')
        )
        # Instead of complicated float formatting, just use Hypothesis floats and format
        # We'll generate floats with limited decimal places and exponent
        float_st = st.floats(min_value=-1e6, max_value=1e6, allow_infinity=False, allow_nan=False).map(
            lambda f: format(f, '.6g')
        )
        # Choose int or float string
        return st.one_of(
            int_part.map(str),
            float_st
        )

    json_number_st = json_number()

    # Forward declare value strategy for recursion
    # We'll use st.recursive to build obj and arr

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string_st,
        json_number_st,
        json_true,
        json_false,
        json_null,
    )

    # Recursive strategy for JSON values
    def json_value():
        # obj and arr will be defined recursively
        # Use st.recursive to limit depth and size
        # obj: { pair (, pair)* } or {}
        # pair: STRING : value
        # arr: [ value (, value)* ] or []

        # pair strategy: STRING : value
        # We'll generate pairs with string keys and json values

        # We'll define value recursively below, so we need a placeholder
        # Use st.deferred to break recursion cycle
        return st.deferred(lambda: json_value_strategy)

    # pair strategy depends on value
    def json_pair():
        return st.tuples(json_string_st, json_value()).map(lambda kv: f"{kv[0]}:{kv[1]}")

    # obj strategy: {} or { pair (, pair)* }
    def json_obj():
        # pairs list max size 0..5 to keep size bounded
        pairs = st.lists(json_pair(), max_size=5)
        return st.one_of(
            st.just("{}"),
            pairs.map(lambda ps: "{" + ",".join(ps) + "}")
        )

    # arr strategy: [] or [ value (, value)* ]
    def json_arr():
        values = st.lists(json_value(), max_size=5)
        return st.one_of(
            st.just("[]"),
            values.map(lambda vs: "[" + ",".join(vs) + "]")
        )

    # Compose recursive value strategy
    json_value_strategy = st.recursive(
        base_values,
        lambda children: st.one_of(
            json_obj(),
            json_arr(),
        ),
        max_leaves=10,
    )

    # Compose full JSON text: value EOF
    json_text = json_value_strategy

    # Draw one example and encode as bytes
    s = draw(json_text)
    return s.encode("utf-8")