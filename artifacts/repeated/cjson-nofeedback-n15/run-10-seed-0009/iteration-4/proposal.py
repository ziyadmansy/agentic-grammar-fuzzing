from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: simplified safe string with escapes
    def json_string():
        # Characters allowed inside strings (excluding control chars and " \)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape: \uXXXX
        hex_digit = st.sampled_from('0123456789abcdefABCDEF')
        unicode_escape = st.tuples(
            st.just('\\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))

        # Either safe char, escape, or unicode escape
        char = st.one_of(
            safe_char.map(lambda c: c),
            escapes,
            unicode_escape,
        )
        # Build string content with length 0..20
        content = st.text(characters=char, min_size=0, max_size=20)
        return content.map(lambda s: '"' + s + '"')

    # NUMBER strategy: use Hypothesis floats and ints, then format to JSON number string
    def json_number():
        # Generate floats and ints in a reasonable range
        # Use floats with finite values, no NaN or inf
        # Format to JSON number string
        def to_json_number(n):
            # Format int without decimal point
            if isinstance(n, int):
                return str(n)
            # Format float with minimal representation
            # Use repr to keep exponent if needed
            return repr(n)

        # Draw int or float
        number = st.one_of(
            st.integers(min_value=-10**6, max_value=10**6),
            st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
        )
        return number.map(to_json_number)

    # Forward declaration for recursive value
    # We'll use st.recursive to build value, obj, arr

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string(),
        json_number(),
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: obj and arr
    # obj: '{' pair (',' pair)* '}' or '{}'
    # pair: STRING ':' value
    # arr: '[' value (',' value)* ']' or '[]'

    # We define pair as STRING ':' value
    # We'll use json_string() for STRING in pair keys

    # To keep recursion bounded, limit max depth and max size of collections

    def json_obj(children):
        # pairs: list of (string, value)
        # max 0..5 pairs
        pairs = st.lists(
            st.tuples(json_string(), children),
            max_size=5,
            unique_by=lambda p: p[0],  # unique keys
        )
        def to_obj(pairs):
            if not pairs:
                return "{}"
            inner = ",".join(f"{k}:{v}" for k, v in pairs)
            return "{" + inner + "}"
        return pairs.map(to_obj)

    def json_arr(children):
        # list of values, max 0..5
        values = st.lists(children, max_size=5)
        def to_arr(values):
            if not values:
                return "[]"
            inner = ",".join(values)
            return "[" + inner + "]"
        return values.map(to_arr)

    # Compose recursive value
    json_value = st.recursive(
        base_values,
        lambda children: st.one_of(
            json_obj(children),
            json_arr(children),
        ),
        max_leaves=10,
    )

    # Compose full JSON with EOF (just the value)
    json_text = json_value

    s = draw(json_text)
    return s.encode("utf-8")