from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and " \)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes
        escapes = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t'
        ])
        # Unicode escape \uXXXX
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: "".join(t))

        # Either a safe char, an escape sequence, or a unicode escape
        json_char = st.one_of(
            safe_char.map(lambda c: c),
            escapes,
            unicode_escape,
        )

        # Build a string of length 0..20 (bounded)
        content = st.lists(json_char, max_size=20).map("".join)
        return content.map(lambda s: f'"{s}"')

    # NUMBER strategy: produce valid JSON numbers as strings
    def json_number():
        # Use Hypothesis built-in floats but convert to JSON number strings
        # Restrict floats to finite numbers, no NaN or inf
        # Also produce integers and floats with exponent
        def to_json_number(n: float) -> str:
            # Format float to JSON number string without trailing .0 if integer
            if n == float('inf') or n == float('-inf') or n != n:
                # fallback to 0 if invalid float
                return "0"
            # Use repr to get shortest representation
            s = repr(n)
            # JSON allows leading minus, digits, optional fraction, optional exponent
            return s

        # Generate floats in a reasonable range to avoid too long exponentials
        floats = st.floats(
            allow_infinity=False,
            allow_nan=False,
            min_value=-1e10,
            max_value=1e10,
            width=32,
        )
        # Also generate integers as strings
        integers = st.integers(min_value=-1_000_000_000, max_value=1_000_000_000)
        # Combine
        return st.one_of(
            floats.map(to_json_number),
            integers.map(str),
        )

    # Recursive JSON value strategy
    def json_value():
        # Use recursive to build nested objects and arrays
        base = st.one_of(
            json_string(),
            json_number(),
            json_true,
            json_false,
            json_null,
        )

        # Recursive containers
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string(),
                    values=children,
                    max_size=3,
                ).map(
                    lambda d: (
                        "{" + 
                        ",".join(f"{k}:{v}" for k, v in d.items()) + 
                        "}" if d else "{}"
                    )
                ),
                # array: [ value (, value)* ] or []
                st.lists(children, max_size=3).map(
                    lambda l: "[" + ",".join(l) + "]" if l else "[]"
                ),
            ),
            max_leaves=10,
        )

    # Draw a JSON value and encode as bytes
    s = draw(json_value())
    return s.encode("utf-8")