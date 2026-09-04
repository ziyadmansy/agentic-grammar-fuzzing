from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING according to grammar: '"' (ESC | SAFECODEPOINT)* '"'
    # We'll approximate ESC and SAFECODEPOINT by allowing safe unicode strings with some escapes.
    # To keep it simple, use st.text with safe characters and some escapes.
    def json_string():
        # Characters excluding control chars and " and \
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Some common escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Compose string with mix of safe chars and escapes
        # Limit length to keep size bounded
        pieces = st.lists(st.one_of(safe_chars.map(lambda c: c), escapes), max_size=10)
        return pieces.map(lambda chars: '"' + ''.join(chars) + '"')

    json_str = json_string()

    # NUMBER: '-'? INT ('.' [0-9]+)? EXP?
    # Use floats and ints, then convert to string
    def json_number():
        # Generate floats and ints, then convert to JSON number string
        # Limit magnitude to keep size bounded
        number = st.one_of(
            st.integers(min_value=-10**6, max_value=10**6),
            st.floats(min_value=-10**6, max_value=10**6, allow_infinity=False, allow_nan=False),
        )
        def to_json_number(n):
            # Format number as JSON number string
            if isinstance(n, int):
                return str(n)
            else:
                # Use repr to get decimal notation, strip trailing zeros if possible
                s = repr(n)
                # repr can produce '1.0', convert to '1' if possible
                if '.' in s:
                    s = s.rstrip('0').rstrip('.')
                    if s == '-0':
                        s = '0'
                return s
        return number.map(to_json_number)

    json_num = json_number()

    # Recursive definition for value: STRING | NUMBER | obj | arr | true | false | null
    # Use st.recursive to build obj and arr

    # Forward declarations for obj and arr
    # We'll define value_strategy inside to allow recursion

    # Define pair: STRING ':' value
    @st.composite
    def pair(draw, value_strategy):
        key = draw(json_str)
        val = draw(value_strategy)
        return f"{key}:{val}"

    def json_obj(value_strategy):
        # obj : '{' pair (',' pair)* '}' | '{' '}'
        # Generate empty or non-empty objects
        pairs = st.lists(pair(value_strategy), max_size=5)
        def to_obj(pairs_list):
            if not pairs_list:
                return "{}"
            else:
                return "{" + ",".join(pairs_list) + "}"
        return pairs.map(to_obj)

    def json_arr(value_strategy):
        # arr : '[' value (',' value)* ']' | '[' ']'
        values = st.lists(value_strategy, max_size=5)
        def to_arr(vals):
            if not vals:
                return "[]"
            else:
                return "[" + ",".join(vals) + "]"
        return values.map(to_arr)

    # Now define value_strategy recursively
    def value_strategy():
        base = st.one_of(
            json_str,
            json_num,
            json_true,
            json_false,
            json_null,
        )
        return st.recursive(
            base,
            lambda children: st.one_of(
                json_obj(children),
                json_arr(children),
            ),
            max_leaves=10,
        )

    val_strat = value_strategy()
    result = draw(val_strat)
    return result.encode("utf-8")