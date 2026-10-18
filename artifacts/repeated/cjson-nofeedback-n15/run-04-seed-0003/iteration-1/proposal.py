from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # SAFECODEPOINT: any char except " \ and control chars (U+0000-U+001F)
    # We'll generate unicode codepoints excluding control chars and " \ 
    def json_string_chars():
        # codepoints excluding control chars and " and \
        # control chars: 0x00-0x1F
        # exclude " (0x22) and \ (0x5C)
        # We'll generate from 0x20 to 0x10FFFF excluding 0x22 and 0x5C
        # To keep it simple, generate from 0x20 to 0x10FFFF and filter out " and \
        return st.characters(
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
            blacklist_characters=['"', '\\'],
            blacklist_categories=['Cc']  # control chars
        )

    # Escape sequences: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
    # We'll produce strings that may contain these escapes.
    # To keep it simple, generate strings of characters or escaped sequences.
    # We'll generate a list of either safe chars or escapes, then join.

    # Escapes as strings
    escapes = st.sampled_from([
        r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t'
    ])

    # Unicode escape: \uXXXX where XXXX are hex digits
    hex_digit = st.characters("0123456789abcdefABCDEF", min_codepoint=0, max_codepoint=0x7F)
    unicode_escape = st.builds(
        lambda a,b,c,d: r'\u' + a + b + c + d,
        hex_digit, hex_digit, hex_digit, hex_digit
    )

    # A single string character can be either a safe codepoint or an escape sequence
    string_char = st.one_of(
        json_string_chars().map(lambda c: c),
        escapes,
        unicode_escape,
    )

    # Compose a string of length 0 to 20 (bounded)
    json_string = st.lists(string_char, max_size=20).map(lambda chars: '"' + ''.join(chars) + '"')

    # NUMBER strategy: produce valid JSON numbers
    # We'll use Hypothesis floats converted to strings, but restrict to JSON number format
    # To keep it simple, generate integers, floats, and exponents as strings

    # Integer part
    int_part = st.one_of(
        st.just("0"),
        st.integers(min_value=1, max_value=10**6).map(str)
    )

    # Fractional part
    frac_part = st.one_of(
        st.just(""),
        st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False).map(
            lambda f: ("%.10f" % f).lstrip("0") if f != 0 else ""
        ).filter(lambda s: s == "" or s.startswith("."))
    )

    # Exponent part
    exp_part = st.one_of(
        st.just(""),
        st.tuples(
            st.sampled_from(["e", "E"]),
            st.sampled_from(["+", "-", ""]),
            st.integers(min_value=0, max_value=1000).map(str)
        ).map(lambda t: t[0] + t[1] + t[2])
    )

    # Compose number string
    def number_string():
        # Compose number string with optional minus
        sign = st.one_of(st.just(""), st.just("-"))
        # integer part: "0" or non-zero integer
        integer = int_part
        # fraction part: "" or .digits
        fraction = st.one_of(st.just(""), st.text(min_size=1, max_size=10, alphabet="0123456789").map(lambda s: "." + s))
        # exponent part: "" or e/E +/- digits
        exponent = st.one_of(st.just(""), st.builds(
            lambda e, s, d: e + s + d,
            st.sampled_from(["e", "E"]),
            st.sampled_from(["+", "-", ""]),
            st.text(min_size=1, max_size=5, alphabet="0123456789")
        ))
        return st.tuples(sign, integer, fraction, exponent).map(lambda parts: "".join(parts))

    json_number = number_string()

    # Forward declaration for recursive structures
    # We'll define value recursively: string, number, obj, arr, true, false, null

    # Use st.recursive to keep recursion bounded

    # Base values
    base_values = st.one_of(
        json_string,
        json_number,
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: obj and arr

    # obj: '{' pair (',' pair)* '}' or '{}'
    # pair: STRING ':' value

    # We'll define pair as a tuple of (string, value)
    # For keys, use json_string without escapes for simplicity (keys are strings)
    key_string = st.text(
        alphabet=st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=['Cc']
        ),
        min_size=1,
        max_size=10
    ).map(lambda s: '"' + s + '"')

    # pair strategy
    @st.composite
    def pair(draw, value_strategy):
        k = draw(key_string)
        v = draw(value_strategy)
        return k + ":" + v

    # obj strategy
    @st.composite
    def obj(draw, value_strategy):
        # generate 0 to 5 pairs
        n = draw(st.integers(min_value=0, max_value=5))
        if n == 0:
            return "{}"
        pairs = [draw(pair(value_strategy)) for _ in range(n)]
        return "{" + ",".join(pairs) + "}"

    # arr strategy
    @st.composite
    def arr(draw, value_strategy):
        n = draw(st.integers(min_value=0, max_value=5))
        if n == 0:
            return "[]"
        values = [draw(value_strategy) for _ in range(n)]
        return "[" + ",".join(values) + "]"

    # Recursive value strategy
    def value_strategy():
        return st.recursive(
            base_values,
            lambda children: st.one_of(
                obj(children),
                arr(children),
            ),
            max_leaves=10,
        )

    val_strat = value_strategy()

    # Compose full json: value + EOF (just value here)
    s = draw(val_strat)
    return s.encode("utf-8")