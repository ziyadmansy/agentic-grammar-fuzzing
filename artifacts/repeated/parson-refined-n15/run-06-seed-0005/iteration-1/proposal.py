from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.from_regex(
        r"-?(0|[1-9]\d*)(\.\d+)?([eE][+-]?\d+)?",
        fullmatch=True,
    )
    # STRING: roughly matching the grammar (no control chars, escapes simplified)
    # We'll generate strings and then escape them properly.
    def json_string():
        # Generate unicode strings without control chars or quotes or backslash
        # Then escape quotes and backslash
        s = st.text(
            alphabet=(
                # Unicode codepoints except control chars and " and \
                # Control chars: U+0000-U+001F
                # Exclude " (0x22) and \ (0x5C)
                # We'll just exclude control and these two explicitly
                st.characters(
                    blacklist_characters=['"', '\\'],
                    blacklist_categories=('Cc',),
                )
            ),
            min_size=0,
            max_size=20,
        )
        def escape_json_string(x: str) -> str:
            # Escape backslash and quote and control chars as per JSON
            # We'll escape backslash and quote, and control chars as \uXXXX
            def esc_char(c):
                if c == '"':
                    return r'\"'
                if c == '\\':
                    return r'\\'
                if ord(c) < 0x20:
                    return r'\u%04x' % ord(c)
                return c
            return '"' + ''.join(esc_char(c) for c in x) + '"'
        return s.map(escape_json_string)

    json_string_st = json_string()

    # Recursive construction of JSON values
    # We limit max depth and size to keep examples bounded

    # Forward declaration for recursion
    # We'll build value strategy recursively
    def json_value():
        # Use recursive to build nested objects and arrays
        base = st.one_of(
            json_string_st,
            json_number,
            json_true,
            json_false,
            json_null,
        )
        # Recursive containers
        # obj: '{' pair (',' pair)* '}' | '{}'
        # pair: STRING ':' value
        # arr: '[' value (',' value)* ']' | '[]'

        # pair strategy: (string, value)
        # We reuse json_string_st for keys (strings)
        # Limit pairs count to keep size bounded
        def pairs_strategy():
            return st.tuples(json_string_st, value).map(
                lambda kv: kv[0] + ':' + kv[1]
            )

        def obj_strategy():
            # 0 to 3 pairs
            pairs = st.lists(pairs_strategy(), max_size=3)
            def build_obj(pairs_list):
                if not pairs_list:
                    return '{}'
                return '{' + ','.join(pairs_list) + '}'
            return pairs.map(build_obj)

        def arr_strategy():
            # 0 to 3 values
            vals = st.lists(value, max_size=3)
            def build_arr(vals_list):
                if not vals_list:
                    return '[]'
                return '[' + ','.join(vals_list) + ']'
            return vals.map(build_arr)

        # Compose recursive strategy
        return st.recursive(
            base,
            lambda children: st.one_of(
                obj_strategy(),
                arr_strategy(),
            ),
            max_leaves=10,
        )

    value = json_value()

    s = draw(value)
    return s.encode('utf-8')