from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then json.dumps them to ensure correctness,
    # but since we cannot import json, we build strings manually.
    # Instead, we generate strings with safe characters and escapes.
    # We'll allow ASCII printable except control chars and backslash/quote, plus some escapes.
    # To keep it simple, generate unicode strings excluding control chars and quotes/backslash,
    # then escape quotes and backslash manually.

    # Characters allowed inside JSON strings (SAFECODEPOINT)
    safe_chars = st.characters(
        blacklist_characters=['"', '\\'],
        blacklist_categories=('Cc',)  # control chars
    )

    # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
    # We'll generate either safe chars or escapes
    def json_string_chars():
        # Escape sequences as strings
        escapes = st.sampled_from([
            r'\"', r'\\', r'\b', r'\f', r'\n', r'\r', r'\t',
            # Unicode escape: \uXXXX where X is hex digit
        ])
        # Unicode escape generator
        hex_digit = st.sampled_from("0123456789abcdefABCDEF")
        unicode_escape = st.tuples(
            st.just(r'\u'),
            hex_digit, hex_digit, hex_digit, hex_digit
        ).map(lambda t: ''.join(t))

        return st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape,
        )

    # Generate a list of 0 to 20 chars for string content
    string_content = st.lists(json_string_chars(), max_size=20).map(''.join)
    json_string = string_content.map(lambda s: f'"{s}"')

    # NUMBER strategy: generate numbers as strings matching grammar
    # We'll generate floats and ints and convert to strings
    def number_to_str(n):
        # Format number to JSON number string
        # Use repr for floats to get exponent notation if needed
        if isinstance(n, int):
            return str(n)
        else:
            # repr(float) gives a valid JSON number representation
            return repr(n)

    json_number = st.one_of(
        st.integers(min_value=-(10**9), max_value=10**9).map(number_to_str),
        st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e9,
            max_value=1e9,
        ).map(number_to_str)
    )

    # Recursive JSON value strategy
    # We'll define a recursive function to build JSON values with bounded depth and size

    # Forward declaration for recursive
    json_value = st.deferred(lambda: json_value_inner)

    # Object: { pair (, pair)* } or {}
    # pair: STRING : value
    # We'll limit number of pairs to max 5 to keep size bounded
    json_pair = st.tuples(json_string, json_value).map(lambda t: f"{t[0]}:{t[1]}")

    json_object = st.one_of(
        st.just("{}"),
        st.lists(json_pair, max_size=5).map(lambda pairs: "{" + ",".join(pairs) + "}")
    )

    # Array: [ value (, value)* ] or []
    json_array = st.one_of(
        st.just("[]"),
        st.lists(json_value, max_size=5).map(lambda values: "[" + ",".join(values) + "]")
    )

    json_value_inner = st.one_of(
        json_string,
        json_number,
        json_object,
        json_array,
        json_true,
        json_false,
        json_null,
    )

    # Generate a full JSON text: value + EOF
    result = draw(json_value)
    return result.encode("utf-8")