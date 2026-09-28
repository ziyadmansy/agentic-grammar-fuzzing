from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode as JSON strings with escapes.
    # To keep it simple, use st.text with safe codepoints and some escapes.
    def json_string():
        # safe codepoints: exclude control chars and quotes/backslash
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # include some escapes by mixing in backslash sequences
        # We'll generate strings that may include backslash + escape char
        # but to keep it simple, just generate normal strings and escape with repr
        # We'll do JSON-style escaping manually below.
        return st.text(safe_chars, min_size=0, max_size=20)

    def escape_json_string(s: str) -> str:
        # Escape according to JSON string rules
        # Replace \, ", control chars, and special escapes
        # Control chars (U+0000 to U+001F) must be escaped as \uXXXX
        # We'll do a simple escape for \ and " and control chars
        res = []
        for c in s:
            o = ord(c)
            if c == '"':
                res.append('\\"')
            elif c == '\\':
                res.append('\\\\')
            elif c == '\b':
                res.append('\\b')
            elif c == '\f':
                res.append('\\f')
            elif c == '\n':
                res.append('\\n')
            elif c == '\r':
                res.append('\\r')
            elif c == '\t':
                res.append('\\t')
            elif 0 <= o <= 0x1F:
                res.append(f'\\u{o:04x}')
            else:
                res.append(c)
        return '"' + "".join(res) + '"'

    json_string_strat = json_string().map(escape_json_string)

    # NUMBER: generate JSON numbers as strings
    # Use hypothesis floats and convert to JSON number strings
    # But limit to finite numbers and reasonable ranges to avoid weird formatting
    def json_number():
        # Generate floats and ints, then convert to JSON number string
        # Also generate ints separately to get integers without decimal point
        int_strat = st.integers(min_value=-10**6, max_value=10**6).map(str)
        float_strat = st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ).map(lambda f: format(f, '.6g'))  # compact float repr
        return st.one_of(int_strat, float_strat)

    json_number_strat = json_number()

    # Recursive JSON value strategy
    # We'll use st.recursive with base = primitives and recurse into arrays and objects

    # Base values: string, number, true, false, null
    base = st.one_of(
        json_string_strat,
        json_number_strat,
        json_true,
        json_false,
        json_null,
    )

    # Forward declarations for recursive
    # Arrays: [ value (, value)* ]
    # Objects: { pair (, pair)* } or empty {}

    # pair: STRING : value
    # We'll generate pairs as "string":value strings

    def json_pair():
        key = json_string_strat
        # value is recursive, so we use a placeholder here and fill later
        # We'll define a helper to build recursive value strategy below
        # For now, return a tuple (key, value_str)
        # We'll build pairs inside the recursive function
        # So this function will be used inside the recursive function
        # We'll implement pairs inside the recursive function below
        raise NotImplementedError

    # Recursive function to build JSON values as strings
    def json_value():
        # We'll define a recursive strategy that returns JSON text (str)
        # Use st.recursive with base and extend with arrays and objects

        def extend_children(children):
            # children is a strategy producing JSON strings
            # arrays: [ value (, value)* ]
            array = children.flatmap(
                lambda vs: st.lists(st.just(vs), min_size=0, max_size=5).map(
                    lambda lst: "[" + ",".join(lst) + "]"
                )
            )
            # objects: { pair (, pair)* } or {}
            # pairs: "string":value
            # We'll generate pairs by combining keys and values from children
            def pairs():
                # keys: strings
                keys = json_string_strat
                # values: children
                return st.tuples(keys, children)

            obj = st.lists(pairs(), min_size=0, max_size=5).map(
                lambda pairs_list: (
                    "{" + ",".join(f"{k}:{v}" for k, v in pairs_list) + "}"
                )
            )
            return st.one_of(array, obj)

        return st.recursive(base, extend_children, max_leaves=10)

    # Use the recursive json_value strategy
    json_strat = json_value()

    # Draw one JSON string and encode as bytes
    s = draw(json_strat)
    return s.encode("utf-8")