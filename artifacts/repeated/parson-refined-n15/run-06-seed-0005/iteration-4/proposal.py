from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_bool = st.one_of(json_true, json_false)

    # JSON string: use safe unicode codepoints excluding control chars and quotes/backslash
    # We mimic SAFECODEPOINT: ~["\\\u0000-\u001F]
    # Use characters from 0x20 (space) to 0x10FFFF excluding backslash and quote
    def safe_char():
        # Unicode range excluding control chars and " \ 
        # We'll exclude codepoints < 0x20, and " (0x22), \ (0x5C)
        # We'll generate from 0x20 to 0x10FFFF and filter out " and \
        return st.characters(
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
            blacklist_characters=['"', '\\'],
            blacklist_categories=['Cc']  # control chars
        )
    json_string = st.text(safe_char(), min_size=0, max_size=20).map(lambda s: '"' + s + '"')

    # JSON number: follow grammar: '-'? INT ('.' [0-9]+)? EXP?
    # Use floats and ints, then format to JSON number string
    def json_number_str():
        # Generate floats and ints with bounded magnitude and digits
        # Use floats with limited decimal places and exponents
        # We'll generate from -1e6 to 1e6 to keep size reasonable
        # Format with minimal representation
        def format_number(n):
            # Format number to JSON number string without trailing zeros in fraction
            if isinstance(n, int):
                return str(n)
            else:
                # Use repr to get shortest representation
                s = repr(n)
                # Remove trailing zeros in fractional part if any
                if '.' in s and 'e' not in s and 'E' not in s:
                    s = s.rstrip('0').rstrip('.')
                return s
        # Draw either int or float
        is_int = draw(st.booleans())
        if is_int:
            n = draw(st.integers(min_value=-10**6, max_value=10**6))
            return format_number(n)
        else:
            # floats with limited decimal places and exponent range
            f = draw(st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False))
            return format_number(f)

    json_number = st.builds(json_number_str)

    # Forward declare value strategy for recursion
    # We'll use st.recursive to build obj and arr

    # Base values: string, number, true, false, null
    base_value = st.one_of(json_string, json_number, json_bool, json_null)

    # Recursive containers: obj and arr
    # obj: '{' pair (',' pair)* '}' or '{}'
    # pair: STRING ':' value
    # arr: '[' value (',' value)* ']' or '[]'

    # We'll define pair as STRING ':' value
    # STRING is json_string (already quoted)
    # value is recursive

    # To avoid infinite recursion and huge outputs, limit max depth and max size

    def json_obj(value):
        # pair: STRING ':' value
        pair = st.tuples(json_string, value).map(lambda p: p[0] + ':' + p[1])
        # zero or more pairs separated by commas
        pairs = st.lists(pair, max_size=4)
        # map to object string
        return pairs.map(lambda ps: '{' + (','.join(ps) if ps else '') + '}')

    def json_arr(value):
        # zero or more values separated by commas
        values = st.lists(value, max_size=4)
        return values.map(lambda vs: '[' + (','.join(vs) if vs else '') + ']')

    json_value = st.recursive(
        base_value,
        lambda children: st.one_of(json_obj(children), json_arr(children)),
        max_leaves=10,
    )

    s = draw(json_value)
    return s.encode('utf-8')