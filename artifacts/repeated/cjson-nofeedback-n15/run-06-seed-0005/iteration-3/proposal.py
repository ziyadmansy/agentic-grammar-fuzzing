from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We limit length to keep size bounded
    def json_string():
        # Characters allowed inside strings (SAFECODEPOINT): exclude control chars, quotes, backslash
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t',
        ])
        # Unicode escape: \uXXXX with hex digits
        hex_digit = st.sampled_from('0123456789abcdefABCDEF')
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))

        # Either a safe char or an escape sequence
        char_or_escape = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Compose string content with length limit
        content = st.lists(char_or_escape, max_size=20).map(''.join)
        return content.map(lambda s: f'"{s}"')

    # NUMBER strategy: generate valid JSON numbers as strings
    def json_number():
        # Use Hypothesis floats converted to JSON number strings with constraints
        # To keep it simple and valid, generate strings matching NUMBER grammar
        # We'll generate integers and floats with optional exponent
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        frac_part = st.one_of(
            st.just(""),
            st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False)
            .map(lambda f: f"{f:.6f}".lstrip("0"))
        )
        # Instead of complex float formatting, build number strings manually:
        # sign + int + optional frac + optional exponent
        sign = st.one_of(st.just(""), st.just("-"))
        exponent = st.one_of(
            st.just(""),
            st.tuples(
                st.sampled_from(["e", "E"]),
                st.one_of(st.just("+"), st.just("-"), st.just("")),
                st.integers(min_value=0, max_value=99).map(str)
            ).map(lambda t: ''.join(t))
        )
        # Compose number string
        def build_number(sign_, int_, frac_, exp_):
            # frac_ might be empty or something like ".123456"
            # frac_ from floats might start with "0." or "."
            # We'll sanitize frac_ to be either "" or ".digits"
            frac_str = ""
            if frac_:
                # Extract digits after decimal point
                if frac_.startswith("0."):
                    frac_str = "." + frac_[2:]
                elif frac_.startswith("."):
                    frac_str = frac_
                else:
                    frac_str = "." + frac_.split(".")[1] if "." in frac_ else ""
                # Remove trailing zeros for neatness
                frac_str = frac_str.rstrip("0")
                if frac_str == ".":
                    frac_str = ""
            return f"{sign_}{int_}{frac_str}{exp_}"

        return st.tuples(sign, int_part, st.just(""), exponent).map(
            lambda t: build_number(*t)
        )

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

    # Recursive strategy for value
    def json_value():
        # Use recursive to build nested arrays and objects
        return st.recursive(
            base_values,
            lambda children: st.one_of(
                # Object: {} or {"pair", ...}
                st.dictionaries(
                    keys=json_string(),
                    values=children,
                    max_size=3,
                ).map(
                    lambda d: (
                        "{" + 
                        ",".join(f"{k}:{v}" for k, v in d.items()) +
                        "}"
                    )
                ),
                # Array: [] or [value, ...]
                st.lists(children, max_size=3).map(
                    lambda l: "[" + ",".join(l) + "]"
                ),
            ),
            max_leaves=10,
        )

    # Compose full JSON: value + EOF (implicit)
    json_str = draw(json_value())
    return json_str.encode("utf-8")