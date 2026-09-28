from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    def json_string():
        # safe codepoints: exclude control chars and " and \
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # escape sequences
        escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # unicode escape: \uXXXX
        hex_digit = st.characters(min_codepoint=0x30, max_codepoint=0x39).filter(lambda c: c in '0123456789abcdefABCDEF')
        unicode_escape = st.tuples(
            st.just('\\u'),
            st.text('0123456789abcdefABCDEF', min_size=4, max_size=4)
        ).map(lambda t: ''.join(t))

        # mix safe chars and escapes/unicode escapes
        # to keep it simple, generate a list of either safe chars or escapes/unicode escapes
        chunk = st.one_of(
            safe_char.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # length bounded to keep size reasonable
        content = st.lists(chunk, min_size=0, max_size=20).map(''.join)
        return content.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # NUMBER strategy: use Hypothesis built-in floats and ints, then format as JSON number strings
    def json_number():
        # Use floats and ints, but format carefully to avoid JSON invalid numbers
        # Generate floats with finite values (no inf/nan)
        # Also generate ints as strings
        int_str = st.integers(min_value=-(10**9), max_value=10**9).map(str)
        float_str = st.floats(allow_nan=False, allow_infinity=False, width=32).map(lambda f: format(f, '.10g'))
        # Combine int or float
        return st.one_of(int_str, float_str)

    json_number_st = json_number()

    # Recursive JSON value strategy
    # Use st.recursive to build nested objects and arrays

    # Forward declaration for value
    # We'll define value as a strategy returning strings representing JSON values

    # obj: '{' pair (',' pair)* '}' or '{}'
    # pair: STRING ':' value

    # arr: '[' value (',' value)* ']' or '[]'

    # We define value as strings representing JSON text

    # To keep recursion bounded, limit max depth and max size of collections

    max_depth = 4
    max_pairs = 5
    max_elements = 5

    def json_value():
        # base cases: string, number, true, false, null
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_true,
            json_false,
            json_null,
        )
        # recursive cases: obj and arr
        def extend(value_st):
            # pair: STRING ':' value
            pair = st.tuples(json_string_st, value_st).map(lambda t: f'{t[0]}:{t[1]}')
            obj = st.lists(pair, max_size=max_pairs).map(
                lambda pairs: '{' + (','.join(pairs) if pairs else '') + '}'
            )
            arr = st.lists(value_st, max_size=max_elements).map(
                lambda elems: '[' + (','.join(elems) if elems else '') + ']'
            )
            return st.one_of(obj, arr)

        return st.recursive(base, extend, max_leaves=100)

    json_st = json_value()

    # Draw a JSON string and encode as UTF-8 bytes
    s = draw(json_st)
    return s.encode('utf-8')