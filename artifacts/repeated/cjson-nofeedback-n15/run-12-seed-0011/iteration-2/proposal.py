from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode them as JSON strings with escapes.
    # To keep it simple, use Hypothesis's built-in json string strategy and tweak it.
    # But since we must produce bytes, we will produce the string and then encode.

    # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
    # We'll allow a subset of unicode excluding control chars and quotes/backslash.
    # To keep it simple, use st.text with min_codepoint=0x20 except quotes and backslash.
    # Then we will escape quotes and backslash manually.

    def json_escape(s: str) -> str:
        # Escape backslash and quotes and control chars as per JSON spec
        def esc_char(c):
            if c == '"':
                return r'\"'
            elif c == '\\':
                return r'\\'
            elif c == '\b':
                return r'\b'
            elif c == '\f':
                return r'\f'
            elif c == '\n':
                return r'\n'
            elif c == '\r':
                return r'\r'
            elif c == '\t':
                return r'\t'
            elif ord(c) < 0x20:
                # Unicode escape for control chars
                return r'\u%04x' % ord(c)
            else:
                return c
        return '"' + ''.join(esc_char(c) for c in s) + '"'

    json_string_raw = st.text(
        alphabet=st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=20,
    )
    json_string = json_string_raw.map(json_escape)

    # NUMBER strategy: produce valid JSON numbers as strings
    # We'll generate floats and ints and format them as JSON numbers
    # To keep it simple, generate ints and floats in reasonable ranges
    json_number_int = st.integers(min_value=-10**6, max_value=10**6).map(str)
    json_number_float = st.floats(
        allow_nan=False, allow_infinity=False, width=32
    ).filter(lambda f: abs(f) < 1e6).map(lambda f: format(f, '.6g'))
    json_number = st.one_of(json_number_int, json_number_float)

    # Recursive JSON value strategy
    # We'll define a recursive strategy for value:
    # value = string | number | obj | arr | true | false | null

    # Forward declaration for recursive
    # We use st.deferred to allow recursion

    # Define obj and arr later using recursive

    # We'll define value as a recursive strategy with bounded depth

    # First define placeholders for obj and arr
    # We'll define them inside the recursive call

    # Compose value strategy
    def json_value():
        return st.deferred(lambda: json_value_strategy)

    # obj: '{' pair (',' pair)* '}' or '{}'
    # pair: STRING ':' value
    # We'll generate dicts with string keys and json_value values

    # arr: '[' value (',' value)* ']' or '[]'
    # We'll generate lists of json_value

    # Compose pair strategy: key is json_string_raw (unescaped), value is json_value
    # We'll generate keys as python strings (no escapes), then encode keys as JSON strings

    # To keep keys simple, limit keys to ascii letters and digits
    json_key = st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')),
        min_size=1,
        max_size=10,
    ).map(json_escape)

    # Now define obj and arr using recursive

    def json_obj():
        # dict with 0 to 5 pairs
        # keys unique
        return st.dictionaries(
            keys=st.text(
                alphabet=st.characters(blacklist_characters=['"', '\\', '\u0000', '\u001F'], min_codepoint=0x20),
                min_size=1,
                max_size=10,
            ),
            values=json_value(),
            min_size=0,
            max_size=5,
            # keys must be unique by definition
        ).map(
            lambda d: (
                '{' +
                ','.join(json_escape(k) + ':' + v for k, v in d.items()) +
                '}'
            )
        )

    def json_arr():
        # list with 0 to 5 elements
        return st.lists(json_value(), min_size=0, max_size=5).map(
            lambda l: '[' + ','.join(l) + ']'
        )

    # Now define value strategy recursively
    json_value_strategy = st.recursive(
        base=st.one_of(
            json_string,
            json_number,
            json_true,
            json_false,
            json_null,
        ),
        extend=lambda children: st.one_of(
            json_obj(),
            json_arr(),
        ),
        max_leaves=10,
    )

    # Compose full json: value + EOF (no trailing chars)
    # We produce the string and encode as utf-8 bytes

    json_text = json_value_strategy

    s = draw(json_text)
    return s.encode('utf-8')