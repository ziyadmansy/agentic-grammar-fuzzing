from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode as JSON strings with escapes.
    # To keep it simple, use Hypothesis's built-in json string strategy.
    json_string = st.text(
        st.characters(
            blacklist_characters=['"', '\\', '\u0000', '\u0001', '\u0002', '\u0003', '\u0004', '\u0005', '\u0006', '\u0007',
                                  '\u0008', '\u000B', '\u000C', '\u000E', '\u000F', '\u0010', '\u0011', '\u0012', '\u0013',
                                  '\u0014', '\u0015', '\u0016', '\u0017', '\u0018', '\u0019', '\u001A', '\u001B', '\u001C',
                                  '\u001D', '\u001E', '\u001F']),
        min_size=0,
        max_size=20,
    )
    # Escape string to JSON string literal
    def to_json_string(s: str) -> str:
        # Escape backslash and quotes, and control chars as \uXXXX
        def esc_char(c):
            if c == '"':
                return '\\"'
            elif c == '\\':
                return '\\\\'
            elif ord(c) < 0x20:
                return '\\u%04x' % ord(c)
            else:
                return c
        return '"' + ''.join(esc_char(c) for c in s) + '"'

    json_string_escaped = json_string.map(to_json_string)

    # NUMBER strategy: generate numbers as strings matching the grammar
    # Use floats and ints, then convert to string with minimal formatting
    def number_to_json(n):
        # Format number to minimal JSON number string
        if isinstance(n, int):
            return str(n)
        else:
            # Use repr to get a JSON-compatible float representation
            s = repr(n)
            # Remove trailing .0 for floats that are integral
            if s.endswith('.0'):
                s = s[:-2]
            return s

    json_number = st.one_of(
        st.integers(min_value=-(10**9), max_value=10**9),
        st.floats(allow_infinity=False, allow_nan=False, width=32, min_value=-1e9, max_value=1e9),
    ).map(number_to_json)

    # Recursive JSON value strategy
    # We'll use st.recursive to build arrays and objects with bounded depth and size

    # Base values: string, number, true, false, null
    base_values = st.one_of(json_string_escaped, json_number, json_true, json_false, json_null)

    # Recursive containers: arrays and objects
    # Arrays: [value, ...]
    # Objects: {"string": value, ...}

    # To keep recursion bounded, limit max depth and max size of containers
    max_depth = 3
    max_size = 5

    def json_value_strategy():
        # Recursive strategy for JSON values
        return st.recursive(
            base_values,
            lambda children: st.one_of(
                st.lists(children, min_size=0, max_size=max_size).map(
                    lambda vs: "[" + ",".join(vs) + "]"
                ),
                st.dictionaries(
                    json_string_escaped.map(lambda s: s[1:-1]),  # strip quotes for keys
                    children,
                    min_size=0,
                    max_size=max_size,
                ).map(
                    lambda d: "{" + ",".join(f'"{k}":{v}' for k, v in d.items()) + "}"
                ),
            ),
            max_leaves=100,
        )

    json_val = json_value_strategy()

    # Compose full JSON text (value + EOF)
    json_text = json_val

    s = draw(json_text)
    return s.encode("utf-8")