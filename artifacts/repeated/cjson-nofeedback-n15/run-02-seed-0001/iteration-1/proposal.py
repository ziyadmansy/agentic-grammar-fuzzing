from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # SAFECODEPOINT: any char except " \ and control chars (U+0000-U+001F)
    # We'll generate unicode codepoints excluding control chars and " and \
    def json_string_chars():
        # exclude control chars, " (0x22), and \ (0x5C)
        # range: U+0020 to U+10FFFF excluding 0x22 and 0x5C
        # For simplicity, limit to BMP (U+0020 to U+FFFF)
        # and exclude surrogates (U+D800-DFFF)
        def char_filter(c):
            o = ord(c)
            if o < 0x20:
                return False
            if c in ['"', '\\']:
                return False
            if 0xD800 <= o <= 0xDFFF:
                return False
            return True
        return st.characters(min_codepoint=0x20, max_codepoint=0xFFFF).filter(char_filter)

    # ESC sequences: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
    # We'll produce strings with a mix of safe chars and escapes
    # To keep it simple, generate strings from a set of safe chars plus some escapes
    # We'll generate a list of chars, each either a safe char or an escape sequence

    # Escape sequences as strings
    escapes = st.sampled_from([
        r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t'
    ])

    # Unicode escape \uXXXX
    def unicode_escape():
        hex_digit = st.sampled_from("0123456789abcdefABCDEF")
        return st.tuples(hex_digit, hex_digit, hex_digit, hex_digit).map(
            lambda t: r'\u' + ''.join(t)
        )

    escape_seq = st.one_of(escapes, unicode_escape())

    # A char can be either a safe codepoint or an escape sequence
    json_string_char = st.one_of(
        json_string_chars().map(lambda c: c),
        escape_seq
    )

    # Generate string content length bounded to keep output size reasonable
    string_content = st.lists(json_string_char, min_size=0, max_size=20).map(''.join)

    json_string = string_content.map(lambda s: '"' + s + '"')

    # NUMBER strategy: produce valid JSON numbers
    # Use Hypothesis floats converted to JSON number strings, or build from grammar
    # We'll build from grammar to keep control:
    # NUMBER : '-'? INT ('.' [0-9]+)? EXP? ;
    # INT : '0' | [1-9][0-9]* ;
    # EXP : [Ee][+-]?[0-9]+ ;

    def json_number():
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        frac_part = st.one_of(
            st.none(),
            st.text(min_size=1, max_size=6, alphabet="0123456789")
        )
        exp_part = st.one_of(
            st.none(),
            st.tuples(
                st.sampled_from("Ee"),
                st.one_of(st.just("+"), st.just("-"), st.just("")),
                st.text(min_size=1, max_size=4, alphabet="0123456789")
            ).map(lambda t: t[0] + t[1] + t[2])
        )
        sign = st.one_of(st.just(""), st.just("-"))

        return st.tuples(sign, int_part, frac_part, exp_part).map(
            lambda t: t[0] + t[1] +
                      (("." + t[2]) if t[2] is not None else "") +
                      (t[3] if t[3] is not None else "")
        )

    json_number_str = json_number()

    # Recursive value strategy
    # value : STRING | NUMBER | obj | arr | 'true' | 'false' | 'null' ;

    # We'll define obj and arr recursively with bounded depth

    # Forward declarations
    def json_value():
        return st.deferred(lambda: json_value_strategy)

    # pair : STRING ':' value ;
    @st.composite
    def json_pair(draw):
        key = draw(json_string)
        val = draw(json_value())
        return key + ":" + val

    # obj : '{' pair (',' pair)* '}' | '{}' ;
    @st.composite
    def json_obj(draw):
        # limit number of pairs to keep size bounded
        pairs = draw(st.lists(json_pair(), max_size=4))
        if not pairs:
            return "{}"
        return "{" + ",".join(pairs) + "}"

    # arr : '[' value (',' value)* ']' | '[]' ;
    @st.composite
    def json_arr(draw):
        values = draw(st.lists(json_value(), max_size=4))
        if not values:
            return "[]"
        return "[" + ",".join(values) + "]"

    # Compose the value strategy with recursion bounded by max_leaves
    json_value_strategy = st.recursive(
        st.one_of(
            json_string,
            json_number_str,
            json_true,
            json_false,
            json_null,
        ),
        lambda children: st.one_of(
            json_obj(),
            json_arr(),
        ),
        max_leaves=10,
    )

    # Compose full json: value + EOF (no trailing data)
    json_text = json_value_strategy

    s = draw(json_text)
    return s.encode("utf-8")