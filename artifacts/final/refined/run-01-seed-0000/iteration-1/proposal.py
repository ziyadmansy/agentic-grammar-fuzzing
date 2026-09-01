from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    def json_string():
        # Characters allowed inside strings (excluding control chars and quotes/backslash)
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escape sequences
        escape_sequences = st.sampled_from([
            r'\"', r'\\', r'\/', r'\b', r'\f', r'\n', r'\r', r'\t'
        ])
        # Unicode escape: \uXXXX
        hex_digit = st.characters("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))

        # Either a safe char, or an escape sequence, or a unicode escape
        string_char = st.one_of(
            safe_char.map(lambda c: c),
            escape_sequences,
            unicode_escape,
        )
        # Compose string content with length 0..20 for bounded size
        content = st.lists(string_char, max_size=20).map(''.join)
        return content.map(lambda s: f'"{s}"')

    # NUMBER strategy: use Hypothesis built-in floats and ints, then convert to JSON number strings
    def json_number():
        # Generate a float or int, then convert to JSON number string
        # Limit range to avoid huge exponents or very long strings
        number = st.one_of(
            st.integers(min_value=-10**6, max_value=10**6),
            st.floats(min_value=-1e6, max_value=1e6, allow_infinity=False, allow_nan=False)
        )
        def to_json_number(n):
            # Format floats to JSON number format without trailing .0 if int
            if isinstance(n, int):
                return str(n)
            else:
                # Use repr to get a JSON-compatible float string
                s = repr(n)
                # Remove trailing zeros and dot if possible
                if '.' in s:
                    s = s.rstrip('0').rstrip('.')
                    if s == '-0':
                        s = '0'
                return s
        return number.map(to_json_number)

    # Forward declaration for recursive value
    # We'll use st.recursive to build obj and arr

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string(),
        json_number(),
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: obj and arr
    # obj: { pair (, pair)* } or {}
    # pair: STRING : value
    # arr: [ value (, value)* ] or []

    # We define pair as a tuple (string, value) then format as JSON pair string

    # We'll define value recursively below

    # Helper to format pair
    def format_pair(pair):
        k, v = pair
        return f"{k}:{v}"

    # Recursive value strategy
    def json_value():
        # Use st.deferred to allow recursion
        return st.deferred(lambda: st.one_of(
            base_values,
            json_obj(),
            json_arr(),
        ))

    # Pair strategy: STRING : value
    json_pair = st.tuples(json_string(), json_value()).map(format_pair)

    # Object strategy
    def json_obj():
        # Empty object or object with 1..5 pairs
        pairs = st.lists(json_pair, max_size=5, unique=True)
        return st.one_of(
            st.just("{}"),
            pairs.map(lambda ps: "{" + ",".join(ps) + "}")
        )

    # Array strategy
    def json_arr():
        # Empty array or array with 1..5 values
        values = st.lists(json_value(), max_size=5)
        return st.one_of(
            st.just("[]"),
            values.map(lambda vs: "[" + ",".join(vs) + "]")
        )

    # Now override json_value to use these
    # We must redefine json_value to avoid infinite recursion
    # Use st.recursive with base_values and containers

    containers = st.deferred(lambda: st.one_of(json_obj(), json_arr()))

    json_value_strategy = st.recursive(
        base_values,
        lambda children: st.one_of(
            # obj with pairs of string and children
            st.lists(st.tuples(json_string(), children), max_size=5).map(
                lambda ps: "{" + ",".join(f"{k}:{v}" for k, v in ps) + "}"
            ),
            # array of children
            st.lists(children, max_size=5).map(
                lambda vs: "[" + ",".join(vs) + "]"
            ),
        ),
        max_leaves=10,
    )

    # Compose full JSON with EOF (just ensure full string)
    json_full = json_value_strategy.map(lambda s: s)

    s = draw(json_full)
    return s.encode("utf-8")