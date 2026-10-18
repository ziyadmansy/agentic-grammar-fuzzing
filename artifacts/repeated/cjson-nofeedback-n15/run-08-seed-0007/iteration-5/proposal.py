from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then JSON-encode them to ensure correctness.
    # But since we can't import json or use eval/exec, we build strings carefully.
    # We'll generate strings with safe characters and some escapes.
    # To keep it simple, generate strings with ASCII printable except control chars and quotes/backslash,
    # plus some escapes.
    safe_chars = st.characters(
        blacklist_characters=['"', '\\'],
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    )
    # Escape sequences: \", \\, \b, \f, \n, \r, \t, \uXXXX
    # We'll randomly insert escapes in strings.
    def json_string():
        # Compose a string with safe chars and occasional escapes
        # To keep it simple, generate a list of either safe char or escape sequence
        escapes = st.sampled_from([
            r'\"', r'\\', r'\b', r'\f', r'\n', r'\r', r'\t',
            # Unicode escape: \uXXXX with hex digits
            lambda: r'\u' + ''.join(draw(st.sampled_from('0123456789abcdefABCDEF')) for _ in range(4))
        ])

        # We can't call draw inside a function like this, so instead:
        # We'll generate a list of elements, each either a safe char or an escape string.
        # We'll generate a list of length up to 20.
        # To do this, define a strategy of elements:
        # - safe char as string
        # - escape string from fixed set (excluding the lambda for unicode)
        # - unicode escape separately

        # Define escape strings excluding unicode first
        simple_escapes = st.sampled_from([r'\"', r'\\', r'\b', r'\f', r'\n', r'\r', r'\t'])
        # Unicode escape: generate \uXXXX
        unicode_escape = st.builds(
            lambda h1,h2,h3,h4: r'\u' + h1 + h2 + h3 + h4,
            st.sampled_from('0123456789abcdefABCDEF'),
            st.sampled_from('0123456789abcdefABCDEF'),
            st.sampled_from('0123456789abcdefABCDEF'),
            st.sampled_from('0123456789abcdefABCDEF'),
        )
        element = st.one_of(
            safe_chars.map(lambda c: c),
            simple_escapes,
            unicode_escape,
        )
        elements = st.lists(element, max_size=20)
        parts = draw(elements)
        return '"' + ''.join(parts) + '"'

    json_string_strategy = st.deferred(json_string)

    # NUMBER strategy: generate valid JSON numbers as strings
    # We'll generate numbers as strings matching the grammar
    def json_number():
        # sign
        sign = st.one_of(st.just(''), st.just('-'))
        # int part
        int_part = st.one_of(
            st.just('0'),
            st.tuples(st.sampled_from('123456789'), st.text(st.characters('0123456789'), max_size=5)).map(lambda t: t[0] + t[1])
        )
        # frac part
        frac_part = st.one_of(st.just(''), st.tuples(st.just('.'), st.text(st.characters('0123456789'), min_size=1, max_size=5)).map(lambda t: t[0] + t[1]))
        # exp part
        exp_part = st.one_of(
            st.just(''),
            st.tuples(
                st.sampled_from('eE'),
                st.one_of(st.just(''), st.sampled_from('+-')),
                st.text(st.characters('0123456789'), min_size=1, max_size=3)
            ).map(lambda t: t[0] + t[1] + t[2])
        )
        return st.tuples(sign, int_part, frac_part, exp_part).map(lambda t: ''.join(t))

    json_number_strategy = st.deferred(json_number)

    # Recursive value strategy
    # We'll use st.recursive to build nested arrays and objects

    # Forward declare value strategy
    # We'll define it inside the function to keep recursion bounded

    def value_strategy():
        base = st.one_of(
            json_string_strategy,
            json_number_strategy,
            json_true,
            json_false,
            json_null,
        )
        # Recursive containers: arrays and objects
        # Array: [ value (, value)* ] or []
        # Object: { pair (, pair)* } or {}
        # pair: STRING : value

        # pair strategy
        pair = st.tuples(json_string_strategy, st.deferred(value_strategy)).map(lambda t: t[0] + ':' + t[1])

        array = st.lists(st.deferred(value_strategy), max_size=4).map(lambda vs: '[' + ','.join(vs) + ']')
        obj = st.lists(pair, max_size=4).map(lambda ps: '{' + ','.join(ps) + '}')

        return st.one_of(base, array, obj)

    val = draw(value_strategy())
    # The top-level json is value + EOF, so val is the whole json text.

    return val.encode('utf-8')