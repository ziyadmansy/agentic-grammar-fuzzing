from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # SAFECODEPOINT: any char except " \ and control chars (U+0000-U+001F)
    # We'll use a subset of unicode excluding control chars and quotes/backslash
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars, ", \)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        # We'll produce either safe chars or escapes
        # For simplicity, generate strings with safe chars plus some escapes
        # Compose a string of length 0..20
        def escape():
            # Choose one escape sequence
            esc_simple = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
            esc_unicode = st.builds(
                lambda h1,h2,h3,h4: '\\u' + h1 + h2 + h3 + h4,
                st.sampled_from('0123456789abcdef'),
                st.sampled_from('0123456789abcdef'),
                st.sampled_from('0123456789abcdef'),
                st.sampled_from('0123456789abcdef'),
            )
            return st.one_of(esc_simple, esc_unicode)

        # Compose string elements: either safe char or escape
        char_or_esc = st.one_of(safe_chars.map(lambda c: c), escape())
        # Build list of 0..20 elements
        return st.lists(char_or_esc, max_size=20).map(lambda chars: '"' + ''.join(chars) + '"')

    json_string_st = json_string()

    # NUMBER strategy: produce valid JSON numbers
    # Use Hypothesis floats converted to JSON number strings, but restrict to finite numbers
    def json_number():
        # Generate numbers as strings matching the grammar:
        # '-'? INT ('.' [0-9]+)? EXP?
        # We'll build strings directly to avoid float formatting issues
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        frac_part = st.one_of(st.just(""), st.floats(min_value=0, max_value=1).map(lambda f: f"{f:.6f}".split('.')[1].rstrip('0')))
        # frac_part above might be empty string, so we filter
        frac_part = st.one_of(
            st.just(""),
            st.integers(min_value=0, max_value=999999).map(lambda i: '.' + str(i).rjust(6, '0').rstrip('0'))
        )
        exp_part = st.one_of(
            st.just(""),
            st.tuples(
                st.sampled_from(['e', 'E']),
                st.sampled_from(['+', '-', '']),
                st.integers(min_value=0, max_value=99)
            ).map(lambda t: t[0] + t[1] + str(t[2]))
        )
        sign_part = st.one_of(st.just(""), st.just("-"))

        return st.builds(
            lambda s, i, f, e: s + i + f + e,
            sign_part, int_part, frac_part, exp_part
        ).filter(lambda s: s != "")

    json_number_st = json_number()

    # Forward declarations for recursive structures
    # We'll use st.recursive to build obj and arr

    # Pair: STRING ':' value
    @st.composite
    def pair(draw, value_st):
        key = draw(json_string_st)
        val = draw(value_st)
        return f"{key}:{val}"

    # obj: '{' pair (',' pair)* '}' | '{}'
    def json_object(value_st):
        # pairs: list of 0..5 pairs
        pairs = st.lists(pair(value_st), max_size=5)
        return pairs.map(lambda ps: "{" + ",".join(ps) + "}" if ps else "{}")

    # arr: '[' value (',' value)* ']' | '[]'
    def json_array(value_st):
        values = st.lists(value_st, max_size=5)
        return values.map(lambda vs: "[" + ",".join(vs) + "]" if vs else "[]")

    # value: STRING | NUMBER | obj | arr | true | false | null
    # We'll build a recursive strategy with bounded depth

    def json_value():
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_true,
            json_false,
            json_null,
        )
        return st.recursive(
            base,
            lambda children: st.one_of(
                json_object(children),
                json_array(children),
            ),
            max_leaves=10,
        )

    val_st = json_value()

    # Compose full json: value + EOF (implicit)
    result = draw(val_st)
    return result.encode("utf-8")