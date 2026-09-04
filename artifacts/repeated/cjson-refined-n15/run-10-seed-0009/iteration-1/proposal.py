from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode as JSON strings with quotes and escapes.
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        # We'll allow a subset of Unicode excluding control chars and quotes/backslash.
        # Also include some escapes.
        # To keep it simple, generate Python strings with safe chars and then json-encode them.
        # But since we can't import json, we manually escape minimal set.
        safe_chars = (
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # Include some escapes by occasionally inserting backslash sequences
        # We'll just generate strings without control chars and quotes/backslash.
        return st.text(safe_chars, min_size=0, max_size=20)

    @st.composite
    def json_string_escaped(draw):
        s = draw(json_string())
        # Escape backslash and quote
        s_esc = s.replace('\\', '\\\\').replace('"', '\\"')
        # Escape control chars if any (shouldn't be present, but just in case)
        # Also escape common escapes: \b, \f, \n, \r, \t randomly
        # For simplicity, just keep as is.
        return '"' + s_esc + '"'

    # NUMBER strategy: generate valid JSON numbers as strings
    # We'll use Hypothesis floats and convert to JSON number strings
    def json_number():
        # Generate floats and ints, then convert to JSON number strings
        # Limit range to avoid scientific notation too large
        def to_json_number(n):
            # Format float/int to JSON number string
            if isinstance(n, int):
                return str(n)
            else:
                # Use repr to get a JSON-compatible float string
                s = repr(n)
                # repr may produce inf/nan, avoid those
                if s in ('inf', '-inf', 'nan', '-nan'):
                    return "0"
                return s

        # Generate ints or floats in reasonable range
        num = st.one_of(
            st.integers(min_value=-10**6, max_value=10**6),
            st.floats(
                allow_infinity=False,
                allow_nan=False,
                min_value=-1e6,
                max_value=1e6,
                width=32,
            ),
        )
        return num.map(to_json_number)

    # Forward declaration for recursive value
    # We'll define value as a recursive strategy
    # Use st.recursive to keep recursion bounded

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string_escaped(),
        json_number(),
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: obj and arr
    # We'll define obj and arr as composites to control size and structure

    @st.composite
    def json_obj(draw):
        # Generate 0 to 5 pairs
        n = draw(st.integers(min_value=0, max_value=5))
        # Generate pairs: STRING : value
        # Keys are strings (json_string_escaped without quotes)
        keys = draw(st.lists(json_string(), min_size=n, max_size=n, unique=True))
        # Values are recursive values
        values = [draw(value) for _ in range(n)]
        # Compose pairs as '"key":value'
        pairs = []
        for k, v in zip(keys, values):
            # Escape key as JSON string
            k_esc = k.replace('\\', '\\\\').replace('"', '\\"')
            key_str = '"' + k_esc + '"'
            pairs.append(f"{key_str}:{v}")
        if pairs:
            return "{" + ",".join(pairs) + "}"
        else:
            return "{}"

    @st.composite
    def json_arr(draw):
        # Generate 0 to 5 elements
        n = draw(st.integers(min_value=0, max_value=5))
        elements = [draw(value) for _ in range(n)]
        return "[" + ",".join(elements) + "]"

    # Now define value recursively
    value = st.recursive(
        base_values,
        lambda children: st.one_of(
            json_obj(),
            json_arr(),
        ),
        max_leaves=10,
    )

    # Compose full JSON: value + EOF (implicit)
    val = draw(value)
    return val.encode("utf-8")