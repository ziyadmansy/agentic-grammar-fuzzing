from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We limit length to keep size bounded
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and " \)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes
        escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Unicode escape sequences
        def unicode_escape():
            hex_digit = st.sampled_from('0123456789abcdefABCDEF')
            return st.tuples(hex_digit, hex_digit, hex_digit, hex_digit).map(
                lambda t: '\\u' + ''.join(t)
            )
        # Mix safe chars and escapes/unicode escapes
        # We'll generate a list of either safe chars or escapes/unicode escapes
        chunk = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape(),
        )
        # Generate a list of chunks, then join and wrap in quotes
        s = st.lists(chunk, min_size=0, max_size=20).map(lambda cs: '"' + ''.join(cs) + '"')
        return s

    json_string_st = json_string()

    # NUMBER strategy: generate numbers as strings matching the grammar
    # We'll use Hypothesis floats and format them carefully
    def json_number():
        # Generate floats in a reasonable range, then format as JSON number string
        # Avoid infinities and NaNs
        f = st.floats(
            allow_infinity=False,
            allow_nan=False,
            min_value=-1e10,
            max_value=1e10,
            width=32,
        )
        def format_number(x: float) -> str:
            # Format float to JSON number string, avoiding trailing .0 if possible
            # Use repr to get a compact representation
            s = repr(x)
            # repr may produce scientific notation, which is valid JSON
            return s
        return f.map(format_number)

    json_number_st = json_number()

    # Recursive JSON value strategy
    # We'll use st.recursive to build nested objects and arrays with bounded depth and size
    def json_value():
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_null,
            json_true,
            json_false,
        )
        # Recursive containers: objects and arrays
        # To keep size bounded, limit number of pairs/elements
        def json_obj():
            # pair: STRING ':' value
            pair = st.tuples(json_string_st, json_value()).map(lambda t: f"{t[0]}:{t[1]}")
            # object: '{' pair (',' pair)* '}' or '{}'
            # limit pairs to max 3 to keep size bounded
            pairs = st.lists(pair, max_size=3)
            return pairs.map(lambda ps: "{" + ",".join(ps) + "}" if ps else "{}")

        def json_arr():
            # array: '[' value (',' value)* ']' or '[]'
            elems = st.lists(json_value(), max_size=3)
            return elems.map(lambda es: "[" + ",".join(es) + "]" if es else "[]")

        return st.recursive(
            base,
            lambda children: st.one_of(json_obj(), json_arr()),
            max_leaves=10,
        )

    # Generate the full JSON text and encode as UTF-8 bytes
    json_text = json_value()
    result = draw(json_text)
    return result.encode("utf-8")