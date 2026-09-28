from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: format(f, '.15g'))
    # JSON numbers can also be integers, so include ints as well
    json_int = st.integers().map(str)
    json_number = st.one_of(json_int, json_number)
    # JSON strings: use Hypothesis text with safe codepoints (exclude control chars and quotes/backslash)
    # SAFECODEPOINT: ~["\\\u0000-\u001F]
    # So exclude control chars (0x00-0x1F), quote (0x22), backslash (0x5C)
    safe_chars = st.characters(
        blacklist_characters=['"', '\\'],
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    )
    json_string = st.text(safe_chars).map(lambda s: '"' + s + '"')

    # Recursive JSON values: value = string | number | obj | arr | true | false | null
    # We'll define obj and arr recursively using st.recursive

    # Forward declarations for obj and arr
    # We'll define value as a recursive strategy below

    # Define pair: STRING ':' value
    @st.composite
    def pair(draw, value_strat):
        key = draw(json_string)
        val = draw(value_strat)
        return f"{key}:{val}"

    # Define obj: '{' pair (',' pair)* '}' | '{}'
    @st.composite
    def obj(draw, value_strat):
        # Choose number of pairs, bounded to keep size small
        n = draw(st.integers(min_value=0, max_value=4))
        if n == 0:
            return "{}"
        pairs = [draw(pair(value_strat)) for _ in range(n)]
        return "{" + ",".join(pairs) + "}"

    # Define arr: '[' value (',' value)* ']' | '[]'
    @st.composite
    def arr(draw, value_strat):
        n = draw(st.integers(min_value=0, max_value=4))
        if n == 0:
            return "[]"
        values = [draw(value_strat) for _ in range(n)]
        return "[" + ",".join(values) + "]"

    # Now define value recursively
    def value_strategy():
        # Base cases
        base = st.one_of(
            json_string,
            json_number,
            json_true,
            json_false,
            json_null,
        )
        # Recursive cases: obj and arr
        return st.recursive(
            base,
            lambda children: st.one_of(
                obj(children),
                arr(children),
            ),
            max_leaves=10,
        )

    val_strat = value_strategy()

    # Draw a full JSON value and append EOF (which is nothing here)
    json_text = draw(val_strat)
    return json_text.encode("utf-8")