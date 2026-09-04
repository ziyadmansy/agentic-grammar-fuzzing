from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes
    # We'll generate Python strings and then encode them as JSON strings
    def json_string():
        # Use characters excluding control chars and backslash, quote
        # We'll allow safe Unicode codepoints except control chars
        # Use st.text with whitelist of safe chars, then json-escape
        # But Hypothesis has no built-in JSON string escaper, so do minimal escaping here
        # We'll generate Python strings and then encode with json.dumps to ensure correctness
        import json as _json
        return st.text(
            st.characters(
                blacklist_characters=['\\', '"', '\u0000', '\u0001', '\u0002', '\u0003', '\u0004', '\u0005', '\u0006', '\u0007',
                                      '\u0008', '\u000b', '\u000c', '\u000e', '\u000f', '\u0010', '\u0011', '\u0012', '\u0013',
                                      '\u0014', '\u0015', '\u0016', '\u0017', '\u0018', '\u0019', '\u001a', '\u001b', '\u001c',
                                      '\u001d', '\u001e', '\u001f'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            ),
            max_size=20,
        ).map(_json.dumps)

    json_string_st = json_string()

    # NUMBER strategy: produce JSON numbers as strings
    # We'll generate Python floats and ints and convert to JSON number strings
    def json_number():
        # Generate ints or floats within reasonable bounds
        # Avoid infinities and NaNs
        # Use st.floats with allow_infinity=False, allow_nan=False
        # Also generate ints
        import math
        def to_json_number(n):
            # Convert number to JSON number string without trailing .0 for ints
            if isinstance(n, int):
                return str(n)
            if isinstance(n, float):
                # Use repr to preserve precision
                s = repr(n)
                # Remove trailing .0 if possible
                if s.endswith(".0"):
                    s = s[:-2]
                return s
            return str(n)
        int_st = st.integers(min_value=-10**6, max_value=10**6)
        float_st = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
        return st.one_of(int_st, float_st).map(to_json_number)

    json_number_st = json_number()

    # Recursive value strategy
    # We'll define a recursive strategy for JSON values:
    # value = string | number | obj | arr | true | false | null

    # Forward declaration of value strategy
    # Use st.deferred to allow recursion
    def json_value():
        return st.deferred(lambda: value_st)

    # Object strategy: { pair (, pair)* } or {}
    # pair = STRING : value
    def json_object():
        # pairs: list of (string, value)
        # Limit max pairs to keep size bounded
        pairs_st = st.dictionaries(
            keys=json_string_st,
            values=json_value(),
            max_size=5,
            # keys must be unique, so dictionary is fine
        )
        def to_json_obj(d):
            # d is dict of json strings (quoted) to json strings (quoted or other)
            # keys and values are JSON encoded strings, so keys are quoted strings
            # We must produce a JSON object string
            # keys are already quoted strings, values are JSON strings
            # So produce: {key:value,...}
            items = []
            for k, v in d.items():
                items.append(f"{k}:{v}")
            return "{" + ",".join(items) + "}"
        return pairs_st.map(to_json_obj)

    # Array strategy: [ value (, value)* ] or []
    def json_array():
        # list of json strings
        elems_st = st.lists(json_value(), max_size=5)
        def to_json_arr(lst):
            return "[" + ",".join(lst) + "]"
        return elems_st.map(to_json_arr)

    # Compose the value strategy with recursion and bounded size
    value_st = st.recursive(
        base=st.one_of(
            json_string_st,
            json_number_st,
            json_true,
            json_false,
            json_null,
        ),
        extend=lambda children: st.one_of(
            json_object(),
            json_array(),
        ),
        max_leaves=10,
    )

    # Draw a value and encode as bytes
    result = draw(value_st)
    return result.encode("utf-8")