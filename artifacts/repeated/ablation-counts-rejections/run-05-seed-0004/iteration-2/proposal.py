from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # JSON string escapes as single characters
    escapes = st.sampled_from(['"', '\\', '/', 'b', 'f', 'n', 'r', 't'])
    # A single escaped character, e.g. \" or \n
    escaped_char = st.builds(lambda c: '\\' + c, escapes)
    # Unicode escape sequence: \uXXXX where X is hex digit
    hex_digit = st.sampled_from('0123456789abcdefABCDEF')
    unicode_escape = st.builds(
        lambda h1, h2, h3, h4: '\\u' + h1 + h2 + h3 + h4,
        hex_digit, hex_digit, hex_digit, hex_digit
    )
    # Safe codepoints: any character except " \ and control chars (0x00-0x1F)
    # We'll generate codepoints from 0x20 to 0x10FFFF excluding " and \
    # But to keep it simple and safe, generate from 0x20 to 0x7E excluding " and \
    safe_char = st.characters(
        blacklist_characters=['"', '\\'],
        min_codepoint=0x20,
        max_codepoint=0x7E,
    )
    # JSON string character: either escaped or safe char
    json_char = st.one_of(escaped_char, unicode_escape, safe_char)
    # JSON string content: 0 to 20 chars to keep size bounded
    json_string_content = st.lists(json_char, max_size=20).map(''.join)
    # JSON string with quotes
    json_string = json_string_content.map(lambda s: '"' + s + '"')

    # JSON number
    # Use Hypothesis built-in floats with constraints, then convert to JSON number string
    # But floats can produce inf/nan, so better to build number strings manually
    # We'll build numbers as strings matching the grammar:
    # NUMBER : '-'? INT ('.' [0-9]+)? EXP? ;
    # INT : '0' | [1-9][0-9]* ;
    # EXP : [Ee][+-]?[0-9]+ ;
    int_part = st.one_of(
        st.just('0'),
        st.builds(lambda d, ds: d + ''.join(ds),
                  st.sampled_from('123456789'),
                  st.lists(st.sampled_from('0123456789'), max_size=5))
    )
    frac_part = st.one_of(
        st.none(),
        st.builds(lambda ds: '.' + ''.join(ds),
                  st.lists(st.sampled_from('0123456789'), min_size=1, max_size=5))
    )
    exp_part = st.one_of(
        st.none(),
        st.builds(lambda e, s, ds: e + s + ''.join(ds),
                  st.sampled_from('eE'),
                  st.sampled_from('+-'),
                  st.lists(st.sampled_from('0123456789'), min_size=1, max_size=3))
    )
    number_str = st.builds(
        lambda sign, i, f, e: (sign or '') + i + (f or '') + (e or ''),
        st.one_of(st.just('-'), st.just('')),
        int_part,
        frac_part,
        exp_part,
    )

    # Forward declaration for recursive value strategy
    # We'll define value_strategy below after obj and arr

    # Pair: STRING ':' value
    # We'll build pair as tuple (string, value) then format later

    # Recursive value strategy
    def value_strategy():
        # We limit recursion depth and size by max_leaves and max_size in recursive
        # We'll build obj and arr recursively
        # obj: '{' pair (',' pair)* '}' or '{}'
        # arr: '[' value (',' value)* ']' or '[]'

        # pair: STRING ':' value
        # We'll build pairs as (string, value) tuples

        # To avoid infinite recursion, define value as recursive with base cases

        base = st.one_of(
            json_string,
            number_str,
            st.just('true'),
            st.just('false'),
            st.just('null'),
        )

        # pair strategy: (string, value)
        pair = st.tuples(json_string, value_strategy()).map(
            lambda t: t[0] + ':' + t[1]
        )

        # obj strategy: either empty or with 1-3 pairs
        obj = st.one_of(
            st.just('{}'),
            st.lists(pair, min_size=1, max_size=3).map(
                lambda pairs: '{' + ','.join(pairs) + '}'
            )
        )

        # arr strategy: either empty or with 1-3 values
        arr = st.one_of(
            st.just('[]'),
            st.lists(value_strategy(), min_size=1, max_size=3).map(
                lambda values: '[' + ','.join(values) + ']'
            )
        )

        return st.one_of(base, obj, arr)

    # Because value_strategy calls itself, we must define it with st.recursive
    # We'll define base and then use st.recursive to build obj and arr

    base = st.one_of(
        json_string,
        number_str,
        st.just('true'),
        st.just('false'),
        st.just('null'),
    )

    def extend(value_strat):
        # pair: STRING ':' value
        pair = st.tuples(json_string, value_strat).map(
            lambda t: t[0] + ':' + t[1]
        )
        obj = st.one_of(
            st.just('{}'),
            st.lists(pair, min_size=1, max_size=3).map(
                lambda pairs: '{' + ','.join(pairs) + '}'
            )
        )
        arr = st.one_of(
            st.just('[]'),
            st.lists(value_strat, min_size=1, max_size=3).map(
                lambda values: '[' + ','.join(values) + ']'
            )
        )
        return st.one_of(obj, arr)

    value = st.recursive(base, extend, max_leaves=10)

    # The top-level json is a value followed by EOF (implicit)
    # We'll generate the value string and encode as bytes
    s = draw(value)
    return s.encode('utf-8')