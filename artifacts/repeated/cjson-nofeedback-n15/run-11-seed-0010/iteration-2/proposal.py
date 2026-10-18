from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode them as JSON strings using repr-like escaping.
    # But Hypothesis has st.text with whitelist_characters, so we can use that.
    # To keep it simple and valid, allow safe Unicode excluding control chars and quotes/backslash.
    safe_chars = (
        chr(i)
        for i in range(0x20, 0xD800)
        if chr(i) not in ['"', '\\']
    )
    safe_chars = ''.join(safe_chars)
    json_string = st.text(safe_chars, min_size=0, max_size=20).map(
        lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
    )

    # NUMBER strategy: generate numbers as strings matching the grammar
    # Use floats and ints, then convert to string with minimal formatting
    def number_to_json(n):
        # Format int without decimal point
        if isinstance(n, int):
            return str(n)
        # Format float with minimal decimal places, no trailing zeros
        s = format(n, '.15g')
        # Ensure exponent is uppercase E
        s = s.replace('e', 'E')
        return s

    json_number = st.one_of(
        st.integers(min_value=-10**6, max_value=10**6).map(number_to_json),
        st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ).map(number_to_json),
    )

    # Forward declaration for recursive value
    # We'll define value recursively below

    # Define value strategy recursively
    def json_value():
        # Base cases: primitives
        base = st.one_of(
            json_string,
            json_number,
            json_null,
            json_true,
            json_false,
        )
        # Recursive cases: obj and arr
        # Use bounded recursion with max_depth=3 to keep sizes small
        return st.recursive(
            base,
            lambda children: st.one_of(
                # obj: { pair (, pair)* } or {}
                st.builds(
                    lambda pairs: "{" + ",".join(pairs) + "}",
                    st.lists(
                        st.tuples(
                            json_string,
                            children,
                        ).map(lambda t: t[0] + ":" + t[1]),
                        max_size=3,
                    ),
                ),
                st.just("{}"),
                # arr: [ value (, value)* ] or []
                st.builds(
                    lambda values: "[" + ",".join(values) + "]",
                    st.lists(children, max_size=3),
                ),
                st.just("[]"),
            ),
            max_leaves=10,
        )

    json_val = json_value()

    # Compose full json with EOF (no trailing data)
    json_full = json_val.map(lambda s: s)

    s = draw(json_full)
    return s.encode("utf-8")