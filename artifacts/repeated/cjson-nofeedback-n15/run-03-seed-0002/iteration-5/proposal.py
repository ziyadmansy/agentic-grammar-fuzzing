from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode them as JSON strings
    # Use a small subset of escapes to keep it simple but valid
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        # We'll generate strings with some escapes by mixing safe chars and escapes
        def escape_seq():
            esc_simple = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
            esc_unicode = st.builds(
                lambda h1,h2,h3,h4: f"\\u{h1}{h2}{h3}{h4}",
                st.sampled_from("0123456789abcdef"),
                st.sampled_from("0123456789abcdef"),
                st.sampled_from("0123456789abcdef"),
                st.sampled_from("0123456789abcdef"),
            )
            return st.one_of(esc_simple, esc_unicode)

        # Compose a string as a list of either safe chars or escapes
        pieces = st.lists(st.one_of(safe_chars.map(lambda c: c), escape_seq()), max_size=20)
        return pieces.map(lambda pieces: '"' + ''.join(pieces) + '"')

    json_string_st = json_string()

    # NUMBER strategy: produce valid JSON numbers as strings
    # Use Hypothesis floats converted to JSON number strings with some control
    def json_number():
        # We'll generate numbers as strings matching the grammar
        # Use floats with limited exponent range and decimal places
        def to_json_number(n: float) -> str:
            # Format float to JSON number string without trailing .0 if integer
            if n == float('inf') or n == float('-inf') or n != n:
                # Avoid infinities and NaN
                return "0"
            s = format(n, '.10g')  # up to 10 significant digits
            # Ensure it matches JSON number grammar (no + sign, no leading zeros except zero itself)
            # Fix leading zeros in exponent
            if 'e' in s or 'E' in s:
                parts = s.lower().split('e')
                base = parts[0]
                exp = parts[1].lstrip('+0') or '0'
                s = base + 'e' + exp
            return s

        # Generate floats in a reasonable range
        return st.floats(min_value=-1e10, max_value=1e10, allow_infinity=False, allow_nan=False).map(to_json_number)

    json_number_st = json_number()

    # Forward declaration for recursive structures
    # We'll use st.recursive to build obj and arr

    # Pair: STRING : value
    @st.composite
    def json_pair(draw, value_st):
        key = draw(json_string_st)
        val = draw(value_st)
        return f"{key}:{val}"

    # Recursive value strategy
    def json_value():
        # Base cases: string, number, true, false, null
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_true,
            json_false,
            json_null,
        )

        # Recursive cases: obj and arr
        def obj_st():
            # obj: {} or { pair (, pair)* }
            # Generate 0 to 3 pairs
            pairs = st.lists(json_pair(value_st), max_size=3)
            return pairs.map(lambda ps: "{" + (",".join(ps) if ps else "") + "}")

        def arr_st():
            # arr: [] or [ value (, value)* ]
            values = st.lists(value_st, max_size=3)
            return values.map(lambda vs: "[" + (",".join(vs) if vs else "") + "]")

        return st.recursive(
            base,
            lambda children: st.one_of(obj_st(), arr_st()),
            max_leaves=10,
        )

    value_st = json_value()

    # The top-level json is a value followed by EOF (whole string)
    json_text = value_st

    s = draw(json_text)
    return s.encode("utf-8")