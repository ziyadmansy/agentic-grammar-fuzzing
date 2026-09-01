from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # SAFECODEPOINT: any Unicode codepoint except control chars and " or \
    # We'll limit to BMP and exclude control chars and " and \
    def json_string_chars():
        # safe chars: codepoints 0x20-0x10FFFF except " and \ and control chars (0x00-0x1F)
        # We'll use a whitelist of visible ASCII + some unicode excluding forbidden
        # For simplicity, use ASCII printable except " and \ plus some escapes
        safe_chars = (
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x7E,
            )
        )
        # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        # We'll produce a mix of safe chars and escapes
        # Compose a strategy that generates a list of chars or escapes
        escape_sequences = st.sampled_from([
            r'\"', r'\\', r'\b', r'\f', r'\n', r'\r', r'\t',
            # Unicode escape \uXXXX with hex digits
            lambda: r'\u' + ''.join(draw(st.sampled_from('0123456789abcdefABCDEF')) for _ in range(4))
        ])

        # To keep it simple, generate a list of either safe chars or escapes
        # We'll generate a list of length 0 to 20
        def char_or_escape():
            # 80% safe char, 20% escape
            return st.one_of(
                safe_chars,
                st.deferred(lambda: st.just(draw(escape_sequences)() if callable(escape_sequences.example()) else draw(escape_sequences)))
            )
        # But the above is complicated, so instead:
        # We'll generate a list of length 0-20 of either safe chars or fixed escapes
        # For unicode escapes, generate separately
        escapes = st.sampled_from([r'\"', r'\\', r'\b', r'\f', r'\n', r'\r', r'\t'])
        unicode_escape = st.builds(
            lambda h1,h2,h3,h4: r'\u' + h1 + h2 + h3 + h4,
            st.sampled_from('0123456789abcdefABCDEF'),
            st.sampled_from('0123456789abcdefABCDEF'),
            st.sampled_from('0123456789abcdefABCDEF'),
            st.sampled_from('0123456789abcdefABCDEF'),
        )
        char_or_escape = st.one_of(safe_chars, escapes, unicode_escape)

        return st.lists(char_or_escape, max_size=20).map(''.join)

    json_string = json_string_chars().map(lambda s: f'"{s}"')

    # NUMBER strategy: match grammar NUMBER: '-'? INT ('.' [0-9]+)? EXP?
    # INT: '0' | [1-9][0-9]*
    # EXP: [Ee][+-]?[0-9]+
    def json_number():
        # INT
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        # optional fraction
        fraction = st.one_of(
            st.just(""),
            st.builds(lambda digits: "." + digits, st.text(min_size=1, max_size=6, alphabet=st.characters(min_codepoint=48, max_codepoint=57)))  # digits
        )
        # optional exponent
        exponent = st.one_of(
            st.just(""),
            st.builds(
                lambda e, sign, digits: e + sign + digits,
                st.sampled_from(["E", "e"]),
                st.one_of(st.just("+"), st.just("-"), st.just("")),
                st.text(min_size=1, max_size=4, alphabet=st.characters(min_codepoint=48, max_codepoint=57))
            )
        )
        # optional minus
        minus = st.one_of(st.just(""), st.just("-"))
        return st.builds(lambda m,i,f,e: m + i + f + e, minus, int_part, fraction, exponent)

    json_number_str = json_number()

    # Recursive JSON value strategy
    # Use st.recursive to keep size bounded
    base = st.one_of(
        json_string,
        json_number_str,
        json_true,
        json_false,
        json_null,
    )

    # Forward declarations for obj and arr
    # pair: STRING ':' value
    # obj: '{' pair (',' pair)* '}' | '{}'
    # arr: '[' value (',' value)* ']' | '[]'

    # We'll define value recursively
    def json_value():
        return st.deferred(lambda: value)

    # pair strategy
    pair = st.tuples(json_string, json_value()).map(lambda p: f"{p[0]}:{p[1]}")

    # obj strategy
    def json_obj():
        # empty or 1-5 pairs
        pairs = st.lists(pair, max_size=5)
        return pairs.map(lambda ps: "{" + ",".join(ps) + "}" if ps else "{}")

    # arr strategy
    def json_arr():
        # empty or 1-5 values
        values = st.lists(json_value(), max_size=5)
        return values.map(lambda vs: "[" + ",".join(vs) + "]" if vs else "[]")

    # Compose recursive value
    value = st.recursive(
        base,
        lambda children: st.one_of(
            json_obj(),
            json_arr(),
        ),
        max_leaves=10,
    )

    # Compose full json with EOF
    json_full = value.map(lambda s: s)

    # Draw and encode to bytes
    s = draw(json_full)
    return s.encode("utf-8")