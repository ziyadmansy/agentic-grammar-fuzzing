from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # JSON string characters: safe codepoints excluding control chars and " \ 
    # We'll generate strings with escaped characters as needed.
    # Define a strategy for JSON strings:
    def json_string():
        # Characters allowed inside JSON strings (excluding " and \ and control chars)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escaped characters
        escape_char = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \uXXXX with hex digits
        unicode_escape = st.builds(
            lambda h1, h2, h3, h4: '\\u' + h1 + h2 + h3 + h4,
            st.sampled_from('0123456789abcdef'),
            st.sampled_from('0123456789abcdef'),
            st.sampled_from('0123456789abcdef'),
            st.sampled_from('0123456789abcdef'),
        )
        # Mix safe chars and escapes
        json_char = st.one_of(
            safe_char.map(lambda c: c),
            escape_char,
            unicode_escape,
        )
        # Compose string content with length limit to keep size bounded
        content = st.lists(json_char, min_size=0, max_size=20).map(''.join)
        return content.map(lambda s: '"' + s + '"')

    # JSON numbers
    json_number = st.floats(
        allow_nan=False, allow_infinity=False,
        width=32
    ).map(lambda f: str(f))

    # JSON booleans and null
    json_const = st.sampled_from(['true', 'false', 'null'])

    # Recursive JSON value strategy
    # We'll define a recursive strategy for JSON values:
    # value = string | number | obj | arr | true | false | null

    # Forward declaration for value
    # Use st.deferred to allow recursion
    @st.composite
    def json_value(draw):
        # To keep recursion bounded, limit max depth
        max_depth = 3

        def value_strategy(depth):
            if depth <= 0:
                # No recursion: only primitives
                return st.one_of(json_string(), json_number, json_const)
            else:
                # Recursive: include objects and arrays
                return st.one_of(
                    json_string(),
                    json_number,
                    json_const,
                    json_object(depth - 1),
                    json_array(depth - 1),
                )

        return draw(value_strategy(max_depth))

    @st.composite
    def json_pair(draw, depth):
        key = draw(json_string())
        val = draw(json_value())
        return f'{key}:{val}'

    @st.composite
    def json_object(draw, depth):
        # Empty or with pairs
        # Limit number of pairs to keep size bounded
        pairs = draw(st.lists(json_pair(depth), max_size=4))
        if not pairs:
            return '{}'
        else:
            return '{' + ','.join(pairs) + '}'

    @st.composite
    def json_array(draw, depth):
        # Empty or with values
        values = draw(st.lists(json_value(), max_size=4))
        if not values:
            return '[]'
        else:
            return '[' + ','.join(values) + ']'

    # Generate the full JSON text (value + EOF)
    json_text = json_value()

    s = draw(json_text)
    return s.encode('utf-8')