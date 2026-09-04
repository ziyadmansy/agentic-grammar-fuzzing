from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and " \)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t',
        ])
        # Unicode escape: \u followed by 4 hex digits
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: "".join(t))

        # Compose string content from safe chars and escapes
        # To keep near-valid cases, sometimes insert invalid escapes (like \x)
        # but mostly valid escapes.
        # We'll bias towards safe_chars and valid escapes.
        char_piece = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Generate a list of 0 to 20 pieces
        pieces = st.lists(char_piece, max_size=20)
        s = draw(pieces)
        return '"' + "".join(s) + '"'

    json_string_st = st.deferred(json_string)

    # NUMBER strategy: produce valid JSON numbers as strings
    def json_number():
        # Use Hypothesis floats but convert to JSON number strings
        # We generate numbers as strings to preserve JSON number format
        # We'll generate integers and floats with optional exponent
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        frac_part = st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)
            .map(lambda f: ("%.10f" % f).lstrip("0"))
            .filter(lambda s: s.startswith("."))
        )
        exp_part = st.one_of(
            st.just(""),
            st.integers(min_value=-100, max_value=100).map(lambda e: "e" + str(e))
        )
        sign_part = st.one_of(st.just(""), st.just("-"))
        # Compose number string
        def compose(sign, integer, frac, exp):
            # frac may be empty or like ".123456"
            # exp may be empty or like "e10"
            return sign + integer + frac + exp

        return st.tuples(sign_part, int_part, frac_part, exp_part).map(
            lambda t: compose(*t)
        )

    json_number_st = json_number()

    # Recursive JSON value strategy
    # We'll use st.recursive to keep size bounded
    # Base cases: string, number, true, false, null
    base = st.one_of(
        json_string_st,
        json_number_st,
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: object and array
    # To keep size bounded, limit max elements in arrays and objects
    def json_object():
        # pair: STRING ':' value
        # Use small dicts with 0-5 pairs
        keys = st.lists(json_string_st, max_size=5, unique=True)
        def make_pairs(keys, values):
            # keys and values are lists of equal length
            pairs = [k + ":" + v for k, v in zip(keys, values)]
            return "{" + ",".join(pairs) + "}"

        return st.deferred(lambda: st.tuples(
            keys,
            st.lists(generated_value, min_size=0, max_size=5)
        ).filter(lambda kv: len(kv[0]) == len(kv[1]))
         .map(lambda kv: make_pairs(kv[0], kv[1]))
        )

    def json_array():
        # array: '[' value (',' value)* ']' or '[]'
        # lists of 0-5 elements
        return st.deferred(lambda: st.lists(generated_value, max_size=5)
                           .map(lambda vs: "[" + ",".join(vs) + "]"))

    # We define generated_value as recursive
    generated_value = st.recursive(
        base,
        lambda children: st.one_of(
            json_object(),
            json_array(),
        ),
        max_leaves=10,
    )

    # Compose full JSON text: value + EOF
    json_text = generated_value

    s = draw(json_text)
    return s.encode("utf-8")