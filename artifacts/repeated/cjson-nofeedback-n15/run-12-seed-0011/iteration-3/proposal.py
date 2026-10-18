from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON tokens
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode as JSON strings with escapes.
    # To keep it simple, use Hypothesis's built-in json string strategy and tweak it.
    # But since we can't import hypothesis.extra, we do a custom safe string:
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        safe_chars = (
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # Escape sequences: \", \\, \b, \f, \n, \r, \t, \uXXXX
        # We'll just rely on json.dumps to produce escapes when needed.
        # So generate unicode strings and then json.dumps them.
        return st.text(safe_chars, min_size=0, max_size=20)

    # NUMBER strategy: generate floats and ints as strings matching the grammar
    # We'll generate Python floats/ints and convert to strings matching JSON number format.
    def json_number():
        # Generate numbers in a reasonable range and convert to JSON number strings
        # Use floats and ints, including negative and exponent forms
        # We'll generate floats and ints and format them accordingly.
        # To keep it simple, generate floats and ints and convert with repr or format.
        # Use st.one_of int and float
        int_str = st.integers(min_value=-10**6, max_value=10**6).map(str)
        float_str = st.floats(
            allow_infinity=False,
            allow_nan=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ).map(lambda f: format(f, '.8g'))  # limit precision to avoid trailing zeros
        return st.one_of(int_str, float_str)

    # Recursive value strategy
    # We'll define a recursive strategy for value:
    # value = STRING | NUMBER | obj | arr | true | false | null

    # Forward declaration for value
    # We'll define obj and arr inside the recursive to keep size bounded.

    # Compose the recursive strategy
    def json_value():
        # Base cases
        base = st.one_of(
            json_null,
            json_true,
            json_false,
            json_number(),
            json_string(),
        )

        # Recursive cases: obj and arr
        # obj: '{' pair (',' pair)* '}' | '{}'
        # pair: STRING ':' value
        # arr: '[' value (',' value)* ']' | '[]'

        # pair strategy
        def pair():
            return st.tuples(json_string(), value).map(lambda p: f'{json.dumps(p[0])}:{p[1]}')

        # obj strategy
        def obj():
            # list of pairs, max length 3 to keep size bounded
            pairs = st.lists(pair(), max_size=3)
            return pairs.map(lambda ps: '{' + ','.join(ps) + '}')

        # arr strategy
        def arr():
            # list of values, max length 3
            vals = st.lists(value, max_size=3)
            return vals.map(lambda vs: '[' + ','.join(vs) + ']')

        # Compose recursive
        return st.recursive(
            base,
            lambda children: st.one_of(obj(), arr()),
            max_leaves=5,
        )

    import json

    # We need to define value as a global variable to use in pair and recursive
    # We'll define a placeholder and then assign it after defining json_value
    # But Hypothesis doesn't allow circular references easily, so we do a trick:

    # Define value as a placeholder
    value = st.deferred(lambda: json_value())

    # Now redefine pair, obj, arr using this value
    def pair():
        return st.tuples(json_string(), value).map(lambda p: f'{json.dumps(p[0])}:{p[1]}')

    def obj():
        pairs = st.lists(pair(), max_size=3)
        return pairs.map(lambda ps: '{' + ','.join(ps) + '}')

    def arr():
        vals = st.lists(value, max_size=3)
        return vals.map(lambda vs: '[' + ','.join(vs) + ']')

    # Now redefine json_value with these
    def json_value():
        base = st.one_of(
            json_null,
            json_true,
            json_false,
            json_number(),
            json_string().map(json.dumps),
        )
        return st.recursive(
            base,
            lambda children: st.one_of(obj(), arr()),
            max_leaves=5,
        )

    # Re-assign value to the new json_value
    value = st.deferred(json_value)

    # Finally, generate the full json text and encode as bytes
    json_text = value

    s = draw(json_text)
    return s.encode("utf-8")