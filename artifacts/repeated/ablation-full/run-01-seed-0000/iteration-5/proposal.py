from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string: use printable characters excluding control and backslash/quote
    # We use a simplified safe string strategy that avoids control chars and escapes
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and " \)
        # We'll allow Unicode codepoints except control chars and " \ (escaped)
        # For simplicity, use ascii_letters, digits, punctuation except " and \
        safe_chars = (
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # Generate a string of length 0 to 20
        s = draw(st.text(safe_chars, min_size=0, max_size=20))
        # Escape backslashes and quotes if any (should be none by construction)
        # But to be safe, replace backslash and quote with escapes
        s_escaped = s.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{s_escaped}"'

    # JSON number: use Hypothesis floats converted to JSON number strings
    def json_number():
        # Generate floats that can be represented as JSON numbers
        # Avoid NaN and infinities
        n = draw(
            st.one_of(
                st.integers(min_value=-(10**9), max_value=10**9).map(str),
                st.floats(
                    allow_nan=False,
                    allow_infinity=False,
                    width=32,
                    min_value=-1e9,
                    max_value=1e9,
                ).map(lambda f: format(f, '.15g')),
            )
        )
        return n

    # Recursive JSON value strategy
    def json_value():
        # Compose the recursive strategy here
        base = st.deferred(lambda: json_value())
        # Base cases: string, number, true, false, null
        base_cases = st.one_of(
            st.builds(lambda: json_string()),
            st.builds(lambda: json_number()),
            json_true,
            json_false,
            json_null,
        )

        # Recursive cases: object and array
        # Object: { pair (, pair)* } or {}
        # Pair: STRING : value
        # Array: [ value (, value)* ] or []

        # Pair strategy
        pair = st.tuples(
            st.builds(lambda: json_string()),
            st.deferred(lambda: json_value()),
        ).map(lambda p: f"{p[0]}:{p[1]}")

        # Object strategy
        obj = st.lists(pair, max_size=5).map(
            lambda pairs: "{" + (",".join(pairs) if pairs else "") + "}"
        )

        # Array strategy
        arr = st.lists(st.deferred(lambda: json_value()), max_size=5).map(
            lambda values: "[" + (",".join(values) if values else "") + "]"
        )

        return st.recursive(
            base_cases,
            lambda children: st.one_of(obj, arr),
            max_leaves=10,
        )

    # Compose full JSON with EOF
    json_str = draw(json_value())
    # Return as bytes
    return json_str.encode("utf-8")