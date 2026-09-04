from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string: use Hypothesis text with safe codepoints excluding control chars and quotes/backslash
    # SAFECODEPOINT: ~["\\\u0000-\u001F]
    # We'll exclude control chars (0x00-0x1F), double quote, and backslash
    safe_chars = st.characters(
        blacklist_characters=['"', '\\'],
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    )
    json_string = st.text(safe_chars).map(lambda s: '"' + s + '"')

    # JSON number: use Hypothesis floats converted to JSON number strings, but restrict to finite numbers
    # We'll generate numbers as strings matching the grammar
    def number_to_json(n: float) -> str:
        # Format float to JSON number string without trailing .0 if integer
        if n == float('inf') or n == float('-inf') or n != n:
            # Avoid NaN and infinities
            return "0"
        if int(n) == n:
            return str(int(n))
        else:
            # Use repr to get a compact representation
            return repr(n)

    json_number = st.floats(
        allow_nan=False, allow_infinity=False, width=32
    ).map(number_to_json)

    # Recursive JSON value strategy
    # We'll use st.recursive to build nested arrays and objects with bounded size

    # Forward declaration for value
    # value = STRING | NUMBER | obj | arr | true | false | null

    # Base values
    base = st.one_of(json_string, json_number, json_null, json_true, json_false)

    # To keep recursion bounded, limit max_leaves and max_depth
    # Compose arrays and objects from values

    # Array: '[' value (',' value)* ']' or '[]'
    def array_strategy():
        # list of values, max size 3 to keep size bounded
        return st.lists(value, max_size=3).map(
            lambda vs: "[" + ",".join(vs) + "]"
        )

    # Object: '{' pair (',' pair)* '}' or '{}'
    # pair: STRING ':' value
    def pair_strategy():
        return st.tuples(json_string, value).map(lambda p: p[0] + ":" + p[1])

    def object_strategy():
        # list of pairs, max size 3
        return st.lists(pair_strategy(), max_size=3).map(
            lambda ps: "{" + ",".join(ps) + "}"
        )

    # Compose value recursively
    value = st.recursive(
        base,
        lambda children: st.one_of(array_strategy(), object_strategy()),
        max_leaves=10,
    )

    # Draw a value and append EOF (nothing) implicitly
    s = draw(value)
    return s.encode("utf-8")