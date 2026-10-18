from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then JSON-encode them to ensure correctness.
    # To keep near-valid cases, sometimes produce strings missing closing quote or with bad escapes.
    def json_string():
        # Valid string: use st.text with safe codepoints, then json.dumps
        # Near-valid: sometimes drop last quote or add invalid escape
        base_str = st.text(
            alphabet=(
                # safe codepoints excluding control chars and quotes/backslash
                ''.join(chr(c) for c in range(0x20, 0x7F) if c not in (0x22, 0x5C))
            ),
            min_size=0,
            max_size=20,
        )
        # Compose a valid JSON string by json.dumps (to add quotes and escapes)
        # But Hypothesis disallows import json in some contexts, so do manual escapes:
        def escape_json_string(s: str) -> str:
            # Escape backslash and quote, and control chars as \uXXXX
            res = []
            for ch in s:
                c = ord(ch)
                if ch == '"':
                    res.append('\\"')
                elif ch == '\\':
                    res.append('\\\\')
                elif c < 0x20:
                    res.append('\\u%04x' % c)
                else:
                    res.append(ch)
            return '"' + ''.join(res) + '"'

        # Compose a strategy that sometimes returns valid string, sometimes near-valid
        valid_str = base_str.map(escape_json_string)

        # Near-valid variants:
        # 1) Missing closing quote
        missing_quote = base_str.map(lambda s: escape_json_string(s)[:-1])
        # 2) Invalid escape: add \q somewhere inside quotes
        def invalid_escape(s: str) -> str:
            esc = escape_json_string(s)
            # Insert \q after first quote
            if len(esc) > 2:
                return esc[:1] + '\\q' + esc[1:]
            else:
                return esc
        invalid_esc = base_str.map(invalid_escape)

        return st.one_of(valid_str, missing_quote, invalid_esc)

    json_string_st = json_string()

    # NUMBER strategy: produce valid and near-valid numbers as strings
    # Valid numbers: use Hypothesis floats and ints converted to JSON number strings
    # Near-valid: missing digits, extra dots, trailing letters
    def json_number():
        # Valid number strings
        valid_number = st.one_of(
            st.integers(min_value=-1_000_000, max_value=1_000_000).map(str),
            st.floats(allow_infinity=False, allow_nan=False, width=32).map(lambda f: format(f, 'g')),
        )

        # Near-valid variants:
        # 1) Trailing dot: "123."
        trailing_dot = st.integers(min_value=0, max_value=1_000_000).map(lambda i: str(i) + '.')
        # 2) Multiple dots: "1.2.3"
        multiple_dots = st.just("1.2.3")
        # 3) Trailing letter: "123a"
        trailing_letter = st.integers(min_value=0, max_value=1_000_000).map(lambda i: str(i) + 'a')

        return st.one_of(valid_number, trailing_dot, multiple_dots, trailing_letter)

    json_number_st = json_number()

    # Recursive value strategy
    # We'll use st.recursive to build obj and arr with bounded depth and size
    # value := STRING | NUMBER | obj | arr | true | false | null

    # Forward declarations for obj and arr
    # We'll define them inside the function to keep scope clean

    # Pair: STRING ':' value
    @st.composite
    def pair(draw):
        key = draw(json_string_st)
        val = draw(value_st)
        return f"{key}:{val}"

    # obj: '{' pair (',' pair)* '}' | '{}'
    @st.composite
    def obj(draw):
        # Decide empty or non-empty
        empty = draw(st.booleans())
        if empty:
            return "{}"
        else:
            # up to 3 pairs to keep size bounded
            n = draw(st.integers(min_value=1, max_value=3))
            pairs = [draw(pair) for _ in range(n)]
            return "{" + ",".join(pairs) + "}"

    # arr: '[' value (',' value)* ']' | '[]'
    @st.composite
    def arr(draw):
        empty = draw(st.booleans())
        if empty:
            return "[]"
        else:
            n = draw(st.integers(min_value=1, max_value=3))
            vals = [draw(value_st) for _ in range(n)]
            return "[" + ",".join(vals) + "]"

    # Define value_st recursively
    # We use st.deferred to allow recursion
    value_st = st.deferred(lambda: st.one_of(
        json_string_st,
        json_number_st,
        obj(),
        arr(),
        json_true,
        json_false,
        json_null,
    ))

    # Compose full json: value + EOF (just value here)
    json_text = draw(value_st)
    return json_text.encode("utf-8")