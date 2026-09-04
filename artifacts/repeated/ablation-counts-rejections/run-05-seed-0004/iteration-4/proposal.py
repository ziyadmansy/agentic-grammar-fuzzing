from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with safe codepoints and escapes
    # We allow empty strings and some escapes
    def json_string():
        # Characters allowed inside strings: SAFECODEPOINT or escapes
        # SAFECODEPOINT: any Unicode codepoint except control chars and " or \
        # We'll simplify: printable ASCII except " and \ plus some escapes
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        # We'll generate either safe_chars or escapes
        # For \uXXXX, generate 4 hex digits
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just("\\u"),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: "".join(t))
        simple_escape = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        escape = st.one_of(simple_escape, unicode_escape)
        # Compose string content as list of safe_chars or escapes
        content_char = st.one_of(safe_chars, escape)
        # Limit length to keep size bounded
        content = st.lists(content_char, max_size=20).map("".join)
        return content.map(lambda s: f'"{s}"')

    # NUMBER strategy: produce valid JSON numbers
    # We'll use Hypothesis floats converted to JSON number strings with bounded size
    def json_number():
        # Generate floats with limited exponent and decimal places
        # Also generate integers
        # We'll generate decimal strings directly to avoid float formatting issues
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        frac_part = st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)
            .map(lambda f: f"{f:.6f}".split(".")[1].rstrip("0"))
            .filter(lambda s: s != "")
            .map(lambda s: "." + s)
        )
        exp_part = st.one_of(
            st.just(""),
            st.integers(min_value=-10, max_value=10).map(lambda e: f"e{e}")
        )
        sign = st.one_of(st.just(""), st.just("-"))
        return st.tuples(sign, int_part, frac_part, exp_part).map(lambda t: "".join(t))

    # Forward declaration for recursive structures
    # We'll define value recursively with bounded depth
    # Use st.recursive to build obj and arr

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string(),
        json_number(),
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: obj and arr
    # obj: '{' pair (',' pair)* '}' or '{}'
    # pair: STRING ':' value
    # arr: '[' value (',' value)* ']' or '[]'

    # We'll define pair as STRING ':' value
    # STRING for pair keys: reuse json_string but restrict length to keep size small
    pair_key = json_string()

    # Recursive value strategy
    def json_value():
        # We'll build recursive strategy here
        # Use st.recursive with base_values and containers
        # Containers depend on value, so we define a function to build them

        # We define containers as functions that take value strategy as argument
        def json_obj(value_strat):
            # pairs: list of pair_key:value_strat
            # limit number of pairs to keep size bounded
            pair = st.tuples(pair_key, value_strat).map(lambda kv: f"{kv[0]}:{kv[1]}")
            pairs = st.lists(pair, max_size=5)
            return pairs.map(lambda ps: "{" + ",".join(ps) + "}" if ps else "{}")

        def json_arr(value_strat):
            # list of values
            values = st.lists(value_strat, max_size=5)
            return values.map(lambda vs: "[" + ",".join(vs) + "]" if vs else "[]")

        return st.recursive(
            base_values,
            lambda children: st.one_of(
                json_obj(children),
                json_arr(children),
            ),
            max_leaves=10,
        )

    value_strat = json_value()

    # The top-level json is value + EOF (EOF is implicit)
    # Return bytes encoded as UTF-8
    json_text = draw(value_strat)
    return json_text.encode("utf-8")