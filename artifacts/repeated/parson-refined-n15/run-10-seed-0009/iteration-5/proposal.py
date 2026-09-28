from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: use Hypothesis built-in json string strategy
    json_string = st.text(
        alphabet=(
            # safe codepoints excluding control chars and backslash, quote
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # NUMBER strategy: generate numbers as strings matching JSON number format
    # Use floats and ints, then convert to string
    def number_to_json(n):
        # Format int or float to JSON number string without trailing .0 if int
        if isinstance(n, int):
            return str(n)
        else:
            # Use repr to keep exponentials, strip trailing zeros if possible
            s = repr(n)
            # repr of float can be like 1.0, 1e-5, etc.
            # JSON allows these formats
            return s

    json_number = st.one_of(
        st.integers(min_value=-1_000_000, max_value=1_000_000),
        st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ),
    ).map(number_to_json)

    # Recursive JSON value strategy
    # Use st.recursive to build nested objects and arrays with bounded depth and size

    # Forward declaration for value
    # We'll define value as a recursive strategy below
    # Compose obj and arr from value

    # Pair: STRING ':' value
    @st.composite
    def pair(draw, value):
        k = draw(json_string)
        v = draw(value)
        return f"{k}:{v}"

    # Object: '{' pair (',' pair)* '}' or '{}'
    @st.composite
    def obj(draw, value):
        # Limit number of pairs to keep size bounded
        pairs = draw(st.lists(pair(value), max_size=5))
        if not pairs:
            return "{}"
        return "{" + ",".join(pairs) + "}"

    # Array: '[' value (',' value)* ']' or '[]'
    @st.composite
    def arr(draw, value):
        elements = draw(st.lists(value, max_size=5))
        if not elements:
            return "[]"
        return "[" + ",".join(elements) + "]"

    # Define value as recursive strategy
    base = st.one_of(
        json_string,
        json_number,
        json_true,
        json_false,
        json_null,
    )

    # Use st.recursive to add obj and arr
    value = st.recursive(
        base,
        lambda children: st.one_of(
            obj(children),
            arr(children),
        ),
        max_leaves=20,
    )

    # Compose full JSON: value + EOF (no trailing chars)
    json_text = value

    s = draw(json_text)
    return s.encode("utf-8")