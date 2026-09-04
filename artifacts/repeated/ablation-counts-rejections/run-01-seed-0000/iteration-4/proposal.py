from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string: use ASCII printable except control chars and backslash/quote for safety
    # We'll escape backslash and quote properly
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars, backslash, quote)
        # We'll generate safe unicode codepoints excluding control chars and backslash/quote
        # For simplicity, limit to ASCII printable except backslash and quote
        safe_chars = st.characters(
            blacklist_characters=['\\', '"'],
            min_codepoint=0x20,
            max_codepoint=0x7E,
        )
        # Generate strings of length 0 to 20
        s = draw(st.text(safe_chars, max_size=20))
        # Escape backslash and quote if any (should be none, but just in case)
        s_escaped = s.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{s_escaped}"'

    # JSON number: use Hypothesis float or int converted to JSON number string
    # We'll generate numbers as strings matching the grammar
    def json_number():
        # Generate integers or floats in a reasonable range
        # Use floats with finite decimal representation to avoid weird exponents
        # We'll generate decimal strings manually
        is_int = draw(st.booleans())
        if is_int:
            n = draw(st.integers(min_value=-10**6, max_value=10**6))
            return str(n)
        else:
            # float with optional exponent
            # generate float as decimal string with optional exponent
            # Use floats with limited decimal places
            f = draw(st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False))
            # Format float with up to 6 decimal places, strip trailing zeros
            s = f"{f:.6f}".rstrip('0').rstrip('.')
            # Possibly add exponent part
            if draw(st.booleans()):
                exp = draw(st.integers(min_value=-10, max_value=10))
                s += f"e{exp:+d}"
            # Handle negative zero edge case
            if s == "-0":
                s = "0"
            return s

    # Recursive JSON value strategy
    def json_value():
        # Base cases: string, number, true, false, null
        base = st.deferred(lambda: st.one_of(
            st.builds(json_string),
            st.builds(json_number),
            json_true,
            json_false,
            json_null,
        ))

        # Recursive cases: object and array
        def json_obj():
            # pair: STRING ':' value
            # Use small dicts to keep size bounded
            # Keys are strings, values are json_value()
            keys = st.lists(
                st.text(
                    st.characters(
                        blacklist_characters=['\\', '"'],
                        min_codepoint=0x20,
                        max_codepoint=0x7E,
                    ),
                    max_size=10,
                ),
                unique=True,
                max_size=5,
            )
            def build_obj(klist):
                pairs = []
                for k in klist:
                    # Escape key string
                    k_esc = k.replace('\\', '\\\\').replace('"', '\\"')
                    key_str = f'"{k_esc}"'
                    val_str = draw(json_value())
                    pairs.append(f"{key_str}:{val_str}")
                if pairs:
                    return "{" + ",".join(pairs) + "}"
                else:
                    return "{}"
            return keys.map(build_obj)

        def json_arr():
            # array of json_value, max size 5
            vals = st.lists(json_value(), max_size=5)
            def build_arr(vlist):
                return "[" + ",".join(vlist) + "]"
            return vals.map(build_arr)

        return st.recursive(
            base,
            lambda children: st.one_of(json_obj(), json_arr()),
            max_leaves=10,
        )

    # Draw the top-level json value and append EOF (nothing)
    result = draw(json_value())
    return result.encode("utf-8")