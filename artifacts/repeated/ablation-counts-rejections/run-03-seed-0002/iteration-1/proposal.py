from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.from_regex(
        r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?",
        fullmatch=True,
    )
    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode them as JSON strings with escapes.
    # To keep it simple, generate unicode strings excluding control chars and quotes/backslash,
    # then escape quotes and backslash manually.
    def json_string():
        # safe codepoints: exclude control chars (<=0x1F), quote (0x22), backslash (0x5C)
        # We'll generate from 0x20 (space) to 0x10FFFF excluding 0x22 and 0x5C
        def safe_char():
            # Unicode codepoints excluding control chars, quote, backslash
            # We'll use a filtered character set
            import string
            allowed = (
                [chr(c) for c in range(0x20, 0x22)] +
                [chr(c) for c in range(0x23, 0x5C)] +
                [chr(c) for c in range(0x5D, 0x7F)]
            )
            # Add some unicode beyond ASCII excluding surrogates and control chars
            # For simplicity, just use ASCII-range safe chars here
            return st.sampled_from(allowed)
        # Compose strings of length 0 to 20
        base_str = st.text(safe_char(), min_size=0, max_size=20)
        # Escape quotes and backslash manually
        def escape_json_string(s: str) -> str:
            # Escape backslash and quote
            s = s.replace("\\", "\\\\").replace('"', '\\"')
            # Also escape control chars if any (should not be present)
            # but just in case, escape \b, \f, \n, \r, \t
            s = s.replace("\b", "\\b").replace("\f", "\\f").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
            return f'"{s}"'
        return base_str.map(escape_json_string)
    json_string = json_string()

    # Recursive JSON value strategy
    # Use st.recursive to build nested arrays and objects with bounded depth
    base = st.one_of(json_null, json_true, json_false, json_number, json_string)

    # pair: STRING ':' value
    # We'll reuse json_string for keys, but keys should be strings without escapes ideally
    # For simplicity, generate keys as ascii letters/digits strings without escapes
    key_char = st.characters(min_codepoint=0x20, max_codepoint=0x7E).filter(
        lambda c: c not in '"\\'
    )
    key_str = st.text(key_char, min_size=1, max_size=10).map(lambda s: f'"{s}"')

    def pairs(draw, value_strat):
        # generate 1 to 5 pairs
        n = draw(st.integers(min_value=1, max_value=5))
        pairs = []
        for _ in range(n):
            k = draw(key_str)
            v = draw(value_strat)
            pairs.append(f"{k}:{v}")
        return ",".join(pairs)

    def json_obj(draw, value_strat):
        # empty or non-empty object
        if draw(st.booleans()):
            return "{}"
        else:
            return "{" + pairs(draw, value_strat) + "}"

    def json_arr(draw, value_strat):
        # empty or non-empty array
        if draw(st.booleans()):
            return "[]"
        else:
            n = draw(st.integers(min_value=1, max_value=5))
            vals = [draw(value_strat) for _ in range(n)]
            return "[" + ",".join(vals) + "]"

    def json_value():
        # recursive strategy for JSON values
        return st.recursive(
            base,
            lambda children: st.one_of(
                st.deferred(lambda: st.builds(json_obj, children)),
                st.deferred(lambda: st.builds(json_arr, children)),
            ),
            max_leaves=10,
        )

    # Compose final JSON string
    json_strat = json_value()

    s = draw(json_strat)
    return s.encode("utf-8")