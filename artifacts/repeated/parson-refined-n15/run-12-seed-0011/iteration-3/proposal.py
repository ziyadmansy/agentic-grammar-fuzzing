from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: use JSON string escaping, limited length and safe chars
    # We'll generate Python strings and then json-encode them
    # but since we can't import json, we do minimal escaping here:
    def json_string(s: str) -> str:
        # Escape backslash and double quote and control chars
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        # Replace control chars with \u00XX
        def esc_char(c):
            if ord(c) < 0x20:
                return "\\u%04x" % ord(c)
            return c
        s = "".join(esc_char(c) for c in s)
        return f'"{s}"'

    # STRING strategy: unicode strings without control chars, length <= 20
    # Use safe codepoints per grammar: SAFECODEPOINT excludes control chars and " \ 
    # We'll generate strings of codepoints >= 0x20 except " and \
    safe_chars = st.characters(
        blacklist_characters=['"', '\\'],
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    )
    json_string_strat = st.text(safe_chars, max_size=20).map(json_string)

    # NUMBER strategy: generate floats and ints, then convert to JSON number string
    # We'll generate numbers in a reasonable range to avoid huge strings
    def number_to_json(n):
        # Format int or float as JSON number string
        if isinstance(n, int):
            return str(n)
        else:
            # Use repr to get JSON-compatible float string
            # but avoid scientific notation for small numbers
            s = repr(n)
            # repr may use scientific notation, which is valid JSON
            return s

    json_number_strat = st.one_of(
        st.integers(min_value=-10**6, max_value=10**6).map(number_to_json),
        st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ).map(number_to_json),
    )

    # Recursive JSON value strategy
    # We'll define a recursive strategy for value:
    # value = string | number | obj | arr | true | false | null

    # Forward declaration for recursive strategy
    # We'll build obj and arr using the value strategy itself

    # To avoid infinite recursion and huge outputs, limit max_depth and max_size

    # Define value strategy with recursion
    def json_value():
        # Base cases: primitives
        base = st.one_of(
            json_string_strat,
            json_number_strat,
            json_true,
            json_false,
            json_null,
        )
        # Recursive cases: obj and arr
        # obj: { pair (, pair)* } or {}
        # pair: STRING : value
        # arr: [ value (, value)* ] or []

        # pair strategy: STRING : value
        pair = st.tuples(json_string_strat, json_value()).map(lambda p: f"{p[0]}:{p[1]}")

        # obj strategy: {} or { pair (, pair)* }
        obj = st.lists(pair, max_size=5).map(
            lambda pairs: "{" + (",".join(pairs) if pairs else "") + "}"
        )

        # arr strategy: [] or [ value (, value)* ]
        arr = st.lists(json_value(), max_size=5).map(
            lambda values: "[" + (",".join(values) if values else "") + "]"
        )

        return st.recursive(base, lambda children: st.one_of(obj, arr), max_leaves=10)

    # Draw a JSON string from the recursive value strategy
    json_str = draw(json_value())

    # Return bytes encoded as UTF-8
    return json_str.encode("utf-8")