from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy matching grammar: '"' (ESC | SAFECODEPOINT)* '"'
    # SAFECODEPOINT: ~["\\\u0000-\u001F]
    # ESC: '\' (["\\/bfnrt] | UNICODE)
    # UNICODE: 'u' HEX HEX HEX HEX
    # HEX: [0-9a-fA-F]

    # We'll generate strings with safe codepoints plus some escapes.
    # To keep it simple and bounded, generate strings of length up to 20.

    def json_string_chars():
        # safe codepoints excluding control chars and " and \
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        simple_escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # unicode escape: \u + 4 hex digits
        hex_digit = st.characters(min_codepoint=0x30, max_codepoint=0x39).filter(lambda c: c in '0123456789abcdefABCDEF')
        unicode_escape = st.tuples(
            st.just('\\u'),
            st.text('0123456789abcdefABCDEF', min_size=4, max_size=4)
        ).map(lambda t: t[0] + t[1])

        # Combine all possible chars inside string
        char_strategy = st.one_of(
            safe_chars.map(lambda c: c),
            simple_escapes,
            unicode_escape,
        )
        return char_strategy

    # Compose string content: list of chars length 0..20
    string_content = st.lists(json_string_chars(), max_size=20).map(''.join)
    json_string = string_content.map(lambda s: f'"{s}"')

    # NUMBER: '-'? INT ('.' [0-9]+)? EXP?
    # INT: '0' | [1-9][0-9]*
    # EXP: [Ee][+-]?[0-9]+

    # We'll generate numbers as strings matching the grammar.

    def json_number():
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        frac_part = st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False).map(lambda f: f"{f}".lstrip("0"))
        )
        # frac_part above is a hack; better to generate '.' + digits
        frac_part = st.one_of(
            st.just(""),
            st.text("0123456789", min_size=1, max_size=6).map(lambda d: "." + d)
        )
        exp_part = st.one_of(
            st.just(""),
            st.tuples(
                st.sampled_from(["E", "e"]),
                st.sampled_from(["+", "-", ""]),
                st.text("0123456789", min_size=1, max_size=4)
            ).map(lambda t: t[0] + t[1] + t[2])
        )
        sign_part = st.one_of(st.just(""), st.just("-"))

        return st.tuples(sign_part, int_part, frac_part, exp_part).map(lambda t: "".join(t))

    json_number_str = json_number()

    # Recursive JSON value strategy
    # Use st.recursive to keep bounded recursion and size

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string,
        json_number_str,
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: object and array
    # object: '{' pair (',' pair)* '}' | '{}'
    # pair: STRING ':' value
    # array: '[' value (',' value)* ']' | '[]'

    # We'll define pair and then obj and arr

    # Forward declaration for value to use in pair
    # We'll define value_strategy below

    @st.composite
    def pair(draw, value_strategy):
        key = draw(json_string)
        val = draw(value_strategy)
        return f"{key}:{val}"

    @st.composite
    def obj(draw, value_strategy):
        # empty or 1..max_pairs pairs
        max_pairs = 5
        n = draw(st.integers(min_value=0, max_value=max_pairs))
        if n == 0:
            return "{}"
        pairs = [draw(pair(value_strategy)) for _ in range(n)]
        return "{" + ",".join(pairs) + "}"

    @st.composite
    def arr(draw, value_strategy):
        max_elems = 5
        n = draw(st.integers(min_value=0, max_value=max_elems))
        if n == 0:
            return "[]"
        elems = [draw(value_strategy) for _ in range(n)]
        return "[" + ",".join(elems) + "]"

    # Now define value_strategy recursively
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

    # Compose full JSON text: value + EOF (implicit)
    json_text = val_strat

    # Draw one example and encode as bytes
    s = draw(json_text)
    return s.encode("utf-8")