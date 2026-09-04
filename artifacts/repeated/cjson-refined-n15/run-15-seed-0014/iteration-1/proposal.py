from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    def json_string():
        # Characters allowed inside strings (excluding control chars and " \)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape \uXXXX with hex digits
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))

        escape = st.one_of(simple_escapes, unicode_escape)

        # Compose string content from safe chars and escapes
        # To keep it simple, generate a list of either safe chars or escapes
        str_char = st.one_of(safe_char.map(lambda c: c), escape)
        # Limit length to keep output bounded
        content = st.lists(str_char, min_size=0, max_size=20).map(''.join)
        return content.map(lambda s: f'"{s}"')

    # NUMBER strategy: produce numbers matching the grammar
    def json_number():
        # Use Hypothesis floats but convert to JSON number strings
        # We generate strings directly to match grammar more exactly
        # Format: -? INT ('.' [0-9]+)? EXP?
        # INT: '0' or non-zero digit followed by digits
        int_part = st.one_of(
            st.just("0"),
            st.tuples(
                st.characters(min_codepoint=ord('1'), max_codepoint=ord('9')),
                st.text(st.digits, max_size=10)
            ).map(lambda t: t[0] + t[1])
        )
        frac_part = st.one_of(st.just(""), st.tuples(st.just("."), st.text(st.digits, min_size=1, max_size=10)).map(lambda t: t[0] + t[1]))
        exp_part = st.one_of(
            st.just(""),
            st.tuples(
                st.sampled_from(["e", "E"]),
                st.one_of(st.just("+"), st.just("-"), st.just("")),
                st.text(st.digits, min_size=1, max_size=5)
            ).map(lambda t: t[0] + t[1] + t[2])
        )
        sign = st.one_of(st.just(""), st.just("-"))
        return st.tuples(sign, int_part, frac_part, exp_part).map(lambda t: ''.join(t))

    # Forward declaration for recursive value
    # We'll use st.recursive to build nested objects and arrays

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string(),
        json_number(),
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: objects and arrays
    # To keep recursion bounded, limit max depth and size

    def json_value():
        # Use recursive strategy with base_values and containers
        return st.recursive(
            base_values,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string(),
                    values=children,
                    min_size=0,
                    max_size=3,
                ).map(lambda d: "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"),
                # array: [ value (, value)* ] or []
                st.lists(children, min_size=0, max_size=3).map(lambda l: "[" + ",".join(l) + "]"),
            ),
            max_leaves=10,
        )

    val = draw(json_value())
    return val.encode("utf-8")