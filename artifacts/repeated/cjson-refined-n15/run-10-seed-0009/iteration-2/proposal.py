from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, '.15g'))
    # JSON strings: roughly matching grammar, allowing escapes and safe codepoints
    # We'll use Hypothesis text with safe unicode codepoints excluding control chars and quotes/backslash
    # plus some escapes inserted manually.
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars, quote, backslash)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # We allow strings of length 0..20 for boundedness
        base = st.text(safe_chars, min_size=0, max_size=20)

        # Insert some escapes randomly
        escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \uXXXX with hex digits
        hex_digit = st.sampled_from('0123456789abcdefABCDEF')
        unicode_escape = st.tuples(hex_digit, hex_digit, hex_digit, hex_digit).map(lambda t: '\\u' + ''.join(t))
        escape_seq = st.one_of(escapes, unicode_escape)

        # Compose string with some escapes inserted at random positions
        def insert_escapes(s):
            # Insert 0 to 3 escapes randomly
            import random
            s = list(s)
            for _ in range(random.randint(0, 3)):
                pos = random.randint(0, len(s))
                esc = draw(escape_seq)
                s.insert(pos, esc)
            return ''.join(s)

        # We cannot use random inside draw, so instead:
        # We'll build a strategy that mixes safe chars and escapes
        # To keep it simple, build a list of 0..20 elements, each either a safe char or an escape sequence
        element = st.one_of(
            safe_chars.map(lambda c: c),
            escape_seq,
        )
        # Compose list of elements length 0..20
        elems = st.lists(element, max_size=20)
        s = draw(elems)
        return '"' + ''.join(s) + '"'

    json_string_st = st.deferred(json_string)

    # Recursive JSON values: string, number, object, array, true, false, null
    # We'll use st.recursive to keep bounded recursion and size

    # Base values
    base = st.one_of(
        json_string_st,
        json_number,
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers
    def json_obj():
        # pair: STRING ':' value
        # We'll generate pairs as (string, value)
        # Limit pairs count to 0..5 for boundedness
        pairs = st.lists(
            st.tuples(json_string_st, json_value),
            max_size=5,
            unique_by=lambda p: p[0],  # keys unique
        )
        return pairs.map(
            lambda ps: '{' + ('' if not ps else ','.join(k + ':' + v for k, v in ps)) + '}'
        )

    def json_arr():
        # array of values, length 0..5
        arr_vals = st.lists(json_value, max_size=5)
        return arr_vals.map(
            lambda vs: '[' + ('' if not vs else ','.join(vs)) + ']'
        )

    # We need to define json_value recursively, so use deferred
    json_value = st.deferred(lambda: st.one_of(
        base,
        json_obj(),
        json_arr(),
    ))

    # Now draw a json_value and append EOF (nothing)
    val = draw(json_value)
    return val.encode('utf-8')