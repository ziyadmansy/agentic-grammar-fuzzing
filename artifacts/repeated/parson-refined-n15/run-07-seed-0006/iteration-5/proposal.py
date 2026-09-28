from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then json-encode them to ensure correctness.
    # But since we can't import json, we'll build strings manually with escapes.
    # To keep it simple, generate strings without control chars and escape quotes and backslashes.

    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Generate a string of length 0..20
        base_str = st.text(safe_chars, max_size=20)

        # Escape quotes and backslashes
        def escape_json_string(s: str) -> str:
            # Escape backslash and quote
            s = s.replace('\\', '\\\\').replace('"', '\\"')
            # Also escape control chars if any (should not be present due to safe_chars)
            return s

        return base_str.map(escape_json_string).map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # NUMBER strategy: generate valid JSON numbers as strings
    # Use Hypothesis floats converted to JSON number strings with bounded size
    # We'll generate integers and floats with optional exponent

    def json_number():
        # Generate int or float as string
        # To keep it simple, generate decimal strings matching the grammar
        # We'll generate floats in range -1e6 to 1e6 with limited decimal places
        def float_to_json_number(f: float) -> str:
            # Format float to minimal JSON number representation
            # Use repr to avoid trailing zeros, but limit exponent range
            s = repr(f)
            # repr can produce inf/nan, filter those out
            if s in ('inf', '-inf', 'nan', '-nan'):
                return "0"
            # Remove + sign from exponent if any
            s = s.replace('+', '')
            return s

        return st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False).map(float_to_json_number)

    json_number_st = json_number()

    # Recursive JSON value strategy
    # We'll use st.recursive to build nested objects and arrays

    # Forward declare value strategy
    # value = STRING | NUMBER | obj | arr | true | false | null

    # Define obj and arr as composites to control recursion and size

    # To keep recursion bounded, limit max depth to 3

    max_depth = 3

    def json_value_strategy(depth=0):
        if depth >= max_depth:
            # At max depth, only primitives
            return st.one_of(json_string_st, json_number_st, json_null, json_true, json_false)
        else:
            # Objects: { pair (, pair)* } or {}
            # pair: STRING : value
            def json_pair():
                return st.tuples(json_string_st, json_value_strategy(depth + 1)).map(
                    lambda kv: f"{kv[0]}:{kv[1]}"
                )

            json_obj = st.one_of(
                st.just("{}"),
                st.lists(json_pair(), min_size=1, max_size=4).map(
                    lambda pairs: "{" + ",".join(pairs) + "}"
                ),
            )

            # Arrays: [ value (, value)* ] or []
            json_arr = st.one_of(
                st.just("[]"),
                st.lists(json_value_strategy(depth + 1), min_size=1, max_size=4).map(
                    lambda vals: "[" + ",".join(vals) + "]"
                ),
            )

            return st.one_of(
                json_string_st,
                json_number_st,
                json_obj,
                json_arr,
                json_null,
                json_true,
                json_false,
            )

    # Draw the full JSON text and encode as bytes
    json_text = draw(json_value_strategy())

    return json_text.encode("utf-8")