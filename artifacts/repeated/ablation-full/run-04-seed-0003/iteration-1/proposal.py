from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: simple safe strings with escapes
    # Use a small subset of safe characters and some escapes
    def json_string():
        # SAFECODEPOINT ~["\\\u0000-\u001F], so exclude control chars and backslash and quote
        safe_chars = st.characters(
            blacklist_characters=['\\', '"'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\b', r'\f', r'\n', r'\r', r'\t',
        ])
        # Unicode escape \uXXXX with hex digits
        hex_digit = st.sampled_from("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: "".join(t))

        # Compose either safe char or escape
        char_piece = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Build string with length 0..20 to keep size bounded
        pieces = st.lists(char_piece, max_size=20)
        s = draw(pieces)
        # Join pieces, some are escapes already strings, some are chars
        # All are strings, so join directly
        joined = "".join(s)
        return f'"{joined}"'

    json_string_st = st.deferred(json_string)

    # NUMBER strategy: use Hypothesis floats and ints formatted as JSON numbers
    # We generate strings that match the NUMBER grammar
    def json_number():
        # Generate int part
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        # Optional fraction
        fraction = st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)
            .map(lambda f: f"{f:.6f}".lstrip("0"))
        )
        # Optional exponent
        exponent = st.one_of(
            st.just(""),
            st.integers(min_value=-10, max_value=10).map(lambda e: f"e{e}" if e >= 0 else f"e{e}")
        )
        # Compose number string
        def build_number():
            sign = draw(st.one_of(st.just(""), st.just("-")))
            i = draw(int_part)
            # fraction as string starting with '.' or empty
            f = draw(fraction)
            # fraction from float might be like '.123456' or ''
            # but floats can produce '0.0' so we normalize
            if f and not f.startswith("."):
                f = "." + f.lstrip("0.")
            e = draw(exponent)
            return sign + i + f + e

        return st.deferred(lambda: st.builds(build_number))

    # Instead of above complicated, use a simpler approach:
    # Use Hypothesis floats and ints, then format as JSON number strings
    json_number_st = st.one_of(
        st.integers(min_value=-10**6, max_value=10**6).map(str),
        st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
        .map(lambda f: format(f, ".6g"))
    )

    # Forward declaration for recursive structures
    json_value = st.deferred(lambda: json_value_inner)

    # JSON pair: STRING : value
    json_pair = st.tuples(json_string_st, json_value).map(lambda t: f"{t[0]}:{t[1]}")

    # JSON object: { pair (, pair)* } or {}
    def json_object():
        # Up to 3 pairs to keep size bounded
        pairs = st.lists(json_pair, max_size=3)
        return pairs.map(lambda ps: "{" + ",".join(ps) + "}" if ps else "{}")

    # JSON array: [ value (, value)* ] or []
    def json_array():
        values = st.lists(json_value, max_size=3)
        return values.map(lambda vs: "[" + ",".join(vs) + "]" if vs else "[]")

    # Compose json_value with recursion bounded by max_leaves
    json_value_inner = st.recursive(
        st.one_of(
            json_string_st,
            json_number_st,
            json_null,
            json_true,
            json_false,
        ),
        lambda children: st.one_of(
            json_object(),
            json_array(),
        ),
        max_leaves=10,
    )

    # Compose full json: value EOF
    json_text = json_value_inner

    s = draw(json_text)
    return s.encode("utf-8")