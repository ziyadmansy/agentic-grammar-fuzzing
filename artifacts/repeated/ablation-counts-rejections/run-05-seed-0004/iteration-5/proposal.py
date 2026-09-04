from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string: use safe unicode codepoints excluding control chars and quotes/backslash
    # We mimic SAFECODEPOINT: ~["\\\u0000-\u001F]
    # Use characters from 0x20 (space) to 0x10FFFF excluding " and \.
    safe_characters = st.characters(
        blacklist_characters='"\\"',
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    )
    json_string = st.text(safe_characters, min_size=0, max_size=20).map(lambda s: '"' + s + '"')

    # JSON number: use Hypothesis built-in floats but convert to JSON number string
    # We'll generate numbers as strings matching the grammar
    def number_to_json(n: float) -> str:
        # Format float to JSON number string without trailing .0 if possible
        # Use repr to keep exponent notation if needed
        s = repr(n)
        # repr can produce inf/nan, avoid those by filtering in strategy
        if s in ("inf", "-inf", "nan", "-nan"):
            return "0"
        return s

    json_number = st.floats(
        allow_nan=False,
        allow_infinity=False,
        width=32,
        min_value=-1e10,
        max_value=1e10,
    ).map(number_to_json)

    # Forward declaration for recursive structures
    # We'll define value recursively: string, number, obj, arr, true, false, null

    # Pair: STRING ':' value
    @st.composite
    def pair(draw):
        key = draw(json_string)
        val = draw(value)
        return f"{key}:{val}"

    # Object: '{' pair (',' pair)* '}' or '{}'
    @st.composite
    def obj(draw):
        # limit number of pairs to keep size bounded
        pairs = draw(st.lists(pair(), max_size=3))
        if pairs:
            return "{" + ",".join(pairs) + "}"
        else:
            return "{}"

    # Array: '[' value (',' value)* ']' or '[]'
    @st.composite
    def arr(draw):
        values = draw(st.lists(value, max_size=3))
        if values:
            return "[" + ",".join(values) + "]"
        else:
            return "[]"

    # Recursive value strategy
    value = st.deferred(lambda: st.one_of(
        json_string,
        json_number,
        obj(),
        arr(),
        json_true,
        json_false,
        json_null,
    ))

    # Draw a full JSON value and append EOF (which is implicit)
    result = draw(value)
    return result.encode("utf-8")