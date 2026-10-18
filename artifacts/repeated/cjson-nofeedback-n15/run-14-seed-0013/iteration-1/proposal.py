from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.from_regex(r'-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?', fullmatch=True)
    # STRING: roughly valid JSON strings with escapes and safe codepoints
    # We'll generate strings with safe unicode codepoints except control chars and quotes/backslash
    def json_string():
        # safe codepoints: exclude control chars (0x00-0x1F), quote (0x22), backslash (0x5C)
        # We'll generate unicode strings avoiding these chars
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Add some escapes with low probability
        def escape_str():
            esc_chars = ['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']
            # Also unicode escapes \uXXXX
            def unicode_escape():
                hex4 = st.text(st.characters("0123456789abcdefABCDEF"), min_size=4, max_size=4)
                return hex4.map(lambda h: '\\u' + h)
            esc = st.one_of(st.sampled_from(esc_chars), unicode_escape())
            return esc
        # Compose string with mix of safe chars and escapes
        # We'll generate a list of length 0..20 of either safe_char or escape_str
        pieces = st.lists(st.one_of(safe_char.map(lambda c: c), escape_str()), max_size=20)
        s = pieces.map(lambda chars: ''.join(chars))
        return s.map(lambda s: '"' + s + '"')

    json_string_st = json_string()

    # Recursive definition for arrays and objects
    # We'll limit depth and size to keep bounded

    # Forward declaration for value
    # We'll use st.deferred to allow recursion
    @st.composite
    def json_value(draw, max_depth=3):
        if max_depth <= 0:
            # Only primitives at max depth
            v = draw(st.one_of(json_string_st, json_number, json_null, json_true, json_false))
            return v
        else:
            # Compose from all value types
            choice = draw(st.integers(min_value=0, max_value=5))
            if choice == 0:
                return draw(json_string_st)
            elif choice == 1:
                return draw(json_number)
            elif choice == 2:
                # object
                return draw(json_object(max_depth - 1))
            elif choice == 3:
                # array
                return draw(json_array(max_depth - 1))
            elif choice == 4:
                return "true"
            else:
                return draw(st.one_of(json_false, json_null))

    @st.composite
    def json_pair(draw, max_depth):
        key = draw(json_string_st)
        val = draw(json_value(max_depth))
        return f"{key}:{val}"

    @st.composite
    def json_object(draw, max_depth):
        # empty or 1..5 pairs
        size = draw(st.integers(min_value=0, max_value=5))
        if size == 0:
            return "{}"
        pairs = []
        for _ in range(size):
            pairs.append(draw(json_pair(max_depth)))
        return "{" + ",".join(pairs) + "}"

    @st.composite
    def json_array(draw, max_depth):
        size = draw(st.integers(min_value=0, max_value=5))
        if size == 0:
            return "[]"
        vals = [draw(json_value(max_depth)) for _ in range(size)]
        return "[" + ",".join(vals) + "]"

    # Generate a full json document (value + EOF)
    result = draw(json_value(max_depth=3))
    return result.encode("utf-8")