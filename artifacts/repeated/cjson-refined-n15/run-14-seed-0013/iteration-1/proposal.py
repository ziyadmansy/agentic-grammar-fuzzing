from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode them as JSON strings
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and " \)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Also allow some escapes by including backslash sequences
        # We'll generate Python strings and then use json.dumps to encode them,
        # but since we can't import json, we do manual escaping here:
        # Instead, to keep it simple, generate strings without control chars or quotes/backslash.
        return st.text(safe_chars, max_size=20)

    # NUMBER strategy: generate numbers as strings matching the grammar
    # We'll generate floats and ints and convert to strings
    def json_number():
        # Generate floats or ints, then convert to string with minimal formatting
        # Use floats with limited exponent range and decimals
        # Also generate negative numbers
        def number_to_str(n):
            # Format number to JSON number string without trailing .0 if int
            if isinstance(n, int):
                return str(n)
            else:
                s = format(n, '.10g')
                # Remove trailing dot if any
                if s.endswith('.'):
                    s = s[:-1]
                return s

        int_strat = st.integers(min_value=-100000, max_value=100000).map(str)
        float_strat = st.floats(
            min_value=-1e6, max_value=1e6,
            allow_nan=False, allow_infinity=False
        ).map(number_to_str)
        return st.one_of(int_strat, float_strat)

    # Recursive value strategy
    # We'll build a recursive strategy for value:
    # value = STRING | NUMBER | obj | arr | true | false | null

    # Forward declaration for recursive
    # We'll limit max_depth to keep sizes bounded
    max_depth = 3

    def json_value():
        # Use recursive strategy with base cases and recursive cases
        base = st.one_of(
            json_string().map(lambda s: f'"{s}"'),
            json_number(),
            json_true,
            json_false,
            json_null,
        )
        # Recursive containers
        def extend_children(children):
            # children is a strategy for values
            # obj: '{' pair (',' pair)* '}' | '{}'
            # pair: STRING ':' value
            pair = st.tuples(json_string(), children).map(
                lambda p: f'"{p[0]}":{p[1]}'
            )
            obj = st.one_of(
                st.just("{}"),
                st.lists(pair, min_size=1, max_size=4).map(
                    lambda pairs: "{" + ",".join(pairs) + "}"
                ),
            )
            # arr: '[' value (',' value)* ']' | '[]'
            arr = st.one_of(
                st.just("[]"),
                st.lists(children, min_size=1, max_size=4).map(
                    lambda vals: "[" + ",".join(vals) + "]"
                ),
            )
            return st.one_of(base, obj, arr)

        return st.recursive(base, extend_children, max_leaves=50)

    val = draw(json_value())
    return val.encode("utf-8")