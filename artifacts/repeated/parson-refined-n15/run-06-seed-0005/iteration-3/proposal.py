from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON strings: use safe unicode codepoints excluding control chars and quotes/backslash
    # We'll generate strings with length up to 20 to keep size bounded
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars, quotes, backslash)
        # SAFECODEPOINT: ~["\\\u0000-\u001F]
        # We'll use a subset of printable ASCII excluding " and \ and control chars
        safe_chars = (
            [chr(c) for c in range(0x20, 0x7F) if c not in (0x22, 0x5C)]
            + ["\u00A0", "\u00A1", "\u00A9", "\u00AE", "\u00B0", "\u00B1", "\u00B5", "\u00B6", "\u00B7"]
        )
        # Also allow escaped chars: \", \\, \b, \f, \n, \r, \t, \uXXXX
        # We'll generate raw strings and escape them ourselves
        raw_str = st.text(alphabet=safe_chars, min_size=0, max_size=20)
        s = draw(raw_str)
        # Escape backslash and quote
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        # Also randomly insert some escaped control chars or unicode escapes with low probability
        # To keep near-valid cases, sometimes insert escapes
        import random
        def maybe_escape(ch):
            if ch == "\\":
                return "\\\\"
            if ch == '"':
                return '\\"'
            return ch
        # Insert some escapes randomly
        res = []
        for ch in s:
            if random.random() < 0.05:
                # Insert an escape sequence
                esc_choices = ['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t']
                esc = draw(st.sampled_from(esc_choices))
                res.append(esc)
            else:
                res.append(ch)
        s = "".join(res)
        return f'"{s}"'

    json_string_st = st.deferred(json_string)

    # JSON numbers: bounded size, integers and floats
    # Use hypothesis floats and ints, then format as JSON number strings
    def json_number():
        # Generate int or float as string
        # Limit magnitude and decimal places to keep size bounded
        is_float = draw(st.booleans())
        if is_float:
            # float with limited decimal places and exponent
            f = draw(st.floats(min_value=-1e6, max_value=1e6, allow_infinity=False, allow_nan=False))
            # Format with up to 6 decimal places, remove trailing zeros
            s = f"{f:.6f}".rstrip('0').rstrip('.')
            # Possibly add exponent
            if draw(st.booleans()):
                exp = draw(st.integers(min_value=-10, max_value=10))
                s += f"e{exp}"
            # Handle negative zero case
            if s == "-0":
                s = "0"
            return s
        else:
            i = draw(st.integers(min_value=-1_000_000, max_value=1_000_000))
            return str(i)

    json_number_st = st.deferred(json_number)

    # Recursive JSON values: string, number, obj, arr, true, false, null
    # Use st.recursive to keep size bounded

    # Base values
    base_values = st.one_of(
        json_string_st,
        json_number_st,
        json_true,
        json_false,
        json_null,
    )

    # Forward declarations for obj and arr
    # We'll define obj and arr as composites to control size and structure

    @st.composite
    def json_value(draw):
        # Use recursive strategy with max depth 3
        def json_value_inner():
            return st.recursive(
                base_values,
                lambda children: st.one_of(
                    json_obj(children),
                    json_arr(children),
                ),
                max_leaves=10,
            )
        val = draw(json_value_inner())
        return val

    @st.composite
    def json_pair(draw, val_st):
        # pair : STRING ':' value ;
        key = draw(json_string_st)
        val = draw(val_st)
        return f"{key}:{val}"

    @st.composite
    def json_obj(draw, val_st):
        # obj : '{' pair (',' pair)* '}' | '{' '}' ;
        # Limit pairs count to keep size bounded
        n = draw(st.integers(min_value=0, max_value=5))
        if n == 0:
            return "{}"
        pairs = [draw(json_pair(val_st)) for _ in range(n)]
        return "{" + ",".join(pairs) + "}"

    @st.composite
    def json_arr(draw, val_st):
        # arr : '[' value (',' value)* ']' | '[' ']' ;
        n = draw(st.integers(min_value=0, max_value=5))
        if n == 0:
            return "[]"
        vals = [draw(val_st) for _ in range(n)]
        return "[" + ",".join(vals) + "]"

    # Compose final json value with recursion bounded
    val = draw(json_value())

    # Compose full json text with EOF
    json_text = val

    # Return bytes
    return json_text.encode("utf-8")