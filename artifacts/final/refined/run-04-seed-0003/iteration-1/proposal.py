from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.from_regex(
        r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?",
        fullmatch=True,
    )
    # STRING: roughly matching the grammar, allowing safe codepoints and escapes
    # We'll keep it simple: strings with safe characters or simple escapes
    # SAFECODEPOINT ~ ~["\\\u0000-\u001F]
    # We'll generate unicode strings excluding control chars and quotes/backslash
    def json_string():
        # Characters allowed inside string: exclude control chars, quote, backslash
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Also allow simple escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        # We'll generate strings with a mix of safe chars and escapes
        # To keep it simple, generate a list of either safe char or escape sequences
        escape_seq = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t'
        ])
        # Unicode escape: \uXXXX with hex digits
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.builds(
            lambda a,b,c,d: f"\\u{a}{b}{c}{d}",
            hex_digit, hex_digit, hex_digit, hex_digit
        )
        escape = st.one_of(escape_seq, unicode_escape)
        char_or_escape = st.one_of(safe_chars.map(lambda c: c), escape)
        # Generate list of length 0..20
        pieces = draw(st.lists(char_or_escape, max_size=20))
        s = "".join(pieces)
        return f'"{s}"'

    json_string_strategy = st.deferred(lambda: st.builds(lambda s: s, st.just(json_string()))).flatmap(
        lambda f: st.just(f())
    )

    # Recursive value strategy
    def json_value():
        # We'll define recursive strategy with bounded depth
        # Use st.recursive with base cases and containers
        base = st.one_of(
            json_string_strategy,
            json_number,
            json_true,
            json_false,
            json_null,
        )
        # Containers: obj and arr
        # obj: '{' pair (',' pair)* '}' or '{}'
        # pair: STRING ':' value
        # arr: '[' value (',' value)* ']' or '[]'

        # pair strategy
        def pair():
            k = json_string_strategy
            v = st.deferred(json_value)
            return st.tuples(k, v).map(lambda kv: f"{kv[0]}:{kv[1]}")

        # obj strategy
        def obj():
            pairs = st.lists(pair(), max_size=3)
            return pairs.map(
                lambda ps: "{" + (",".join(ps) if ps else "") + "}"
            )

        # arr strategy
        def arr():
            values = st.lists(st.deferred(json_value), max_size=3)
            return values.map(
                lambda vs: "[" + (",".join(vs) if vs else "") + "]"
            )

        containers = st.one_of(obj(), arr())

        return st.recursive(base, lambda children: containers, max_leaves=10)

    val = draw(json_value())
    # The grammar requires json : value EOF
    # So val is the full JSON text
    return val.encode("utf-8")