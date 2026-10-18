from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode them as JSON strings
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',),  # control chars
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Also allow some escapes
        # We'll generate strings with safe chars and occasionally insert escapes
        # To keep it simple, generate unicode strings and then json-encode them
        return st.text(safe_chars, min_size=0, max_size=20).map(
            lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
        )

    json_string_st = json_string()

    # NUMBER strategy: generate numbers as strings matching the grammar
    # We'll generate floats and ints and convert to strings
    def json_number():
        # Generate floats and ints, then convert to JSON number strings
        # Limit magnitude and decimal places to keep size bounded
        return st.one_of(
            st.integers(min_value=-10**6, max_value=10**6).map(str),
            st.floats(
                allow_infinity=False,
                allow_nan=False,
                width=32,
                min_value=-1e6,
                max_value=1e6,
            ).map(lambda f: format(f, '.6g'))
        )

    json_number_st = json_number()

    # Recursive value strategy
    # Use st.recursive to build nested objects and arrays, bounded in size
    def json_value():
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_null,
            json_true,
            json_false,
        )

        # Compose obj and arr recursively
        def json_obj():
            # pair: STRING ':' value
            # We'll generate pairs with string keys and values from json_value
            # Limit number of pairs to keep size bounded
            pair = st.tuples(json_string_st, json_value()).map(
                lambda kv: kv[0] + ':' + kv[1]
            )
            # Object with zero or more pairs separated by commas
            return st.lists(pair, max_size=4).map(
                lambda pairs: '{' + (','.join(pairs) if pairs else '') + '}'
            )

        def json_arr():
            # Array of zero or more values separated by commas
            return st.lists(json_value(), max_size=4).map(
                lambda vals: '[' + (','.join(vals) if vals else '') + ']'
            )

        return st.recursive(
            base,
            lambda children: st.one_of(json_obj(), json_arr()),
            max_leaves=10,
        )

    val = draw(json_value())
    return val.encode('utf-8')