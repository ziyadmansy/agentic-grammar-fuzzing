from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We include some escapes and unicode escapes to cover ESC and UNICODE fragments
    def json_string():
        # safe codepoints exclude control chars and " and \
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # escape sequences: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t',
        ])
        # unicode escape: \uXXXX with hex digits
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: "".join(t))

        # Compose a character that is either safe_char, an escape, or a unicode escape
        char_piece = st.one_of(
            safe_char.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Generate a list of 0 to 20 such pieces to keep size bounded
        pieces = st.lists(char_piece, max_size=20)
        return pieces.map(lambda chars: '"' + "".join(chars) + '"')

    json_string_st = json_string()

    # NUMBER strategy: follow grammar for NUMBER
    def json_number():
        # INT: '0' or non-zero digit followed by digits
        int_part = st.one_of(
            st.just("0"),
            st.tuples(
                st.characters(min_codepoint=49, max_codepoint=57),  # '1'-'9'
                st.text(st.characters(min_codepoint=48, max_codepoint=57), max_size=10)
            ).map(lambda t: t[0] + t[1])
        )
        # optional fraction
        fraction = st.one_of(
            st.just(""),
            st.tuples(
                st.just("."),
                st.text(st.characters(min_codepoint=48, max_codepoint=57), min_size=1, max_size=10)
            ).map(lambda t: t[0] + t[1])
        )
        # optional exponent
        exponent = st.one_of(
            st.just(""),
            st.tuples(
                st.sampled_from(["e", "E"]),
                st.sampled_from(["+", "-"]).optional(),
                st.text(st.characters(min_codepoint=48, max_codepoint=57), min_size=1, max_size=5)
            ).map(lambda t: t[0] + (t[1] or "") + t[2])
        )
        # optional leading minus
        sign = st.one_of(st.just(""), st.just("-"))
        return st.tuples(sign, int_part, fraction, exponent).map(lambda parts: "".join(parts))

    json_number_st = json_number()

    # Recursive JSON value strategy
    # Use st.recursive to build obj and arr from base values
    base = st.one_of(
        json_string_st,
        json_number_st,
        json_true,
        json_false,
        json_null,
    )

    # Forward declarations for obj and arr to be used in value
    # We'll define them inside the recursive function

    def json_obj():
        # pair: STRING ':' value
        # We reuse json_string_st for STRING keys (must be strings)
        # Limit pairs to max 5 to keep size bounded
        pair = st.tuples(json_string_st, st.just(":"), value).map(lambda t: t[0] + t[1] + t[2])
        pairs = st.lists(pair, max_size=5)
        # obj: '{' pair (',' pair)* '}' or '{}'
        return pairs.map(lambda ps: "{" + ",".join(ps) + "}")

    def json_arr():
        # arr: '[' value (',' value)* ']' or '[]'
        values = st.lists(value, max_size=5)
        return values.map(lambda vs: "[" + ",".join(vs) + "]")

    # We define value recursively here
    # Use st.deferred to allow recursion
    value = st.deferred(lambda: st.one_of(
        base,
        json_obj(),
        json_arr(),
    ))

    # Compose full JSON text with EOF (no trailing chars)
    json_text = value.map(lambda s: s)

    # Draw one example and encode as bytes
    s = draw(json_text)
    return s.encode("utf-8")