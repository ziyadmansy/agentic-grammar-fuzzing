from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # SAFECODEPOINT ~["\\\u0000-\u001F], i.e. no control chars, no " or \
    # ESC: \ followed by one of ["\/bfnrt] or \uXXXX
    # We'll generate strings with a mix of safe chars and escapes.
    def json_string_chars():
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes: simple ones and unicode escapes
        simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \uXXXX with hex digits
        hex_digit = st.sampled_from("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))
        # Choose either safe char or escape
        return st.one_of(
            safe_chars.map(lambda c: c),
            simple_escapes,
            unicode_escape,
        )

    @st.composite
    def json_string(draw):
        # Generate a list of chars (length 0 to 20)
        chars = draw(st.lists(json_string_chars(), max_size=20))
        s = ''.join(chars)
        return f'"{s}"'

    # NUMBER strategy: follow grammar NUMBER : '-'? INT ('.' [0-9]+)? EXP? ;
    # INT : '0' | [1-9][0-9]* ;
    # EXP : [Ee][+-]?[0-9]+ ;
    @st.composite
    def json_number(draw):
        negative = draw(st.booleans())
        # INT
        int_part = draw(st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        ))
        # Fractional part
        frac_part = draw(st.one_of(
            st.none(),
            st.floats(min_value=0, allow_infinity=False, allow_nan=False).map(lambda f: f"{f}".partition('.')[2]).filter(lambda x: x != '')
        ))
        if frac_part is not None:
            frac_str = '.' + frac_part
        else:
            frac_str = ''
        # Exponent part
        exp_part = draw(st.one_of(
            st.none(),
            st.tuples(
                st.sampled_from(['E', 'e']),
                st.sampled_from(['+', '-', '']),
                st.integers(min_value=0, max_value=1000).map(str)
            ).map(lambda t: ''.join(t))
        ))
        exp_str = exp_part if exp_part is not None else ''
        number_str = ('-' if negative else '') + int_part + frac_str + exp_str
        return number_str

    # Forward declaration for recursive structures
    # We'll use st.recursive to build value
    # value = STRING | NUMBER | obj | arr | true | false | null

    # obj : '{' pair (',' pair)* '}' | '{' '}' ;
    # pair : STRING ':' value ;
    # arr : '[' value (',' value)* ']' | '[' ']' ;

    # We'll define value_base first (non-recursive)
    value_base = st.deferred(lambda: st.one_of(
        json_string(),
        json_number(),
        json_null,
        json_true,
        json_false,
    ))

    # Recursive strategy for value
    def json_value():
        # pair: STRING ':' value
        @st.composite
        def pair(draw):
            k = draw(json_string())
            v = draw(value)
            return f"{k}:{v}"

        # obj
        @st.composite
        def obj(draw):
            # empty or with pairs
            empty = draw(st.booleans())
            if empty:
                return "{}"
            else:
                # up to 3 pairs to keep size bounded
                pairs = draw(st.lists(pair(), max_size=3, min_size=1))
                return "{" + ",".join(pairs) + "}"

        # arr
        @st.composite
        def arr(draw):
            empty = draw(st.booleans())
            if empty:
                return "[]"
            else:
                # up to 3 values
                vals = draw(st.lists(value, max_size=3, min_size=1))
                return "[" + ",".join(vals) + "]"

        return st.one_of(
            value_base,
            obj(),
            arr(),
        )

    value = st.recursive(value_base, lambda children: st.one_of(
        # obj
        st.deferred(lambda: st.composite(
            lambda draw: (
                "{}" if draw(st.booleans()) else
                "{" + ",".join(
                    draw(st.lists(
                        st.tuples(json_string(), children),
                        max_size=3,
                        min_size=1
                    )).map(lambda pairs: [f"{k}:{v}" for k, v in pairs])
                ) + "}"
            )
        )()),
        # arr
        st.deferred(lambda: st.composite(
            lambda draw: (
                "[]" if draw(st.booleans()) else
                "[" + ",".join(draw(st.lists(children, max_size=3, min_size=1))) + "]"
            )
        )()),
    ), max_leaves=10)

    # Compose full json with EOF
    json_str = draw(value)
    # Return as bytes
    return json_str.encode("utf-8")