from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic terminals
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly valid JSON strings with escapes and safe codepoints
    # We'll generate unicode strings excluding control chars and quotes/backslash,
    # and add some escapes.
    def json_string():
        # safe codepoints: exclude control chars (0x00-0x1F), quote, backslash
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # escape sequences: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t',
        ])
        # unicode escape \uXXXX with hex digits
        hex_digit = st.sampled_from("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: "".join(t))

        # mix safe chars and escapes/unicode escapes
        # to keep it simple, generate a list of either safe chars or escapes
        char_piece = st.one_of(
            safe_char.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # generate 0 to 20 chars inside string
        pieces = st.lists(char_piece, max_size=20)
        s = draw(pieces)
        return '"' + "".join(s) + '"'

    json_string_st = st.deferred(json_string)

    # NUMBER: use Hypothesis floats converted to JSON number strings
    # but limit to finite numbers and reasonable ranges
    def json_number():
        # generate floats but exclude nan/inf
        f = st.floats(allow_nan=False, allow_infinity=False, width=32)
        # convert to JSON number string
        def to_json_number(x):
            # format to JSON number string, avoid scientific notation for small ints
            # but allow exponent for large/small floats
            # Use repr to keep precision, then strip trailing zeros if decimal
            s = repr(x)
            # repr may produce 'inf' or 'nan' but filtered above
            # ensure JSON number format: no leading +, no trailing dot
            if 'e' in s or 'E' in s:
                # normalize exponent to lowercase e
                s = s.lower()
            if '.' in s:
                # strip trailing zeros and dot if needed
                s = s.rstrip('0').rstrip('.')
                if s == '-0':
                    s = '0'
            return s
        return f.map(to_json_number)

    json_number_st = json_number()

    # Recursive JSON value strategy
    # Use st.recursive to build nested arrays and objects
    # Limit max depth and size to keep output bounded

    # Base values: string, number, true, false, null
    base = st.one_of(
        json_string_st,
        json_number_st,
        json_true,
        json_false,
        json_null,
    )

    # Forward declaration for value
    # We'll build arrays and objects recursively

    # Pair: STRING ':' value
    @st.composite
    def pair(draw):
        k = draw(json_string_st)
        v = draw(value)
        return f"{k}:{v}"

    # Object: '{' pair (',' pair)* '}' or '{}'
    @st.composite
    def obj(draw):
        # generate 0 to 5 pairs
        pairs = draw(st.lists(pair(), max_size=5))
        if pairs:
            return "{" + ",".join(pairs) + "}"
        else:
            return "{}"

    # Array: '[' value (',' value)* ']' or '[]'
    @st.composite
    def arr(draw):
        vals = draw(st.lists(value, max_size=5))
        if vals:
            return "[" + ",".join(vals) + "]"
        else:
            return "[]"

    # Now define value recursively
    value = st.recursive(
        base,
        lambda children: st.one_of(
            obj(),
            arr(),
        ),
        max_leaves=10,
    )

    # Compose full json: value + EOF (implicit)
    result = draw(value)
    return result.encode("utf-8")