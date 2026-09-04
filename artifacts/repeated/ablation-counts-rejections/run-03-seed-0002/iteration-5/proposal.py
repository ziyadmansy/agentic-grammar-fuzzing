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
        # Characters allowed inside JSON strings (excluding control chars and " \)
        # We'll include some escapes to preserve near-valid cases
        # Use a small subset of escapes to keep complexity manageable
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        # We'll generate strings that may contain these escapes by mixing raw chars and escapes
        # To keep it simple, generate Python strings and then json.dumps them
        # But we cannot import json, so we manually escape

        # Instead, generate unicode strings without control chars and then escape manually
        # We'll generate strings of length 0..20 to keep size bounded
        return st.text(
            alphabet=st.characters(
                blacklist_characters=['"', '\\', '\u0000', '\u0001', '\u0002', '\u0003', '\u0004', '\u0005', '\u0006', '\u0007',
                                      '\u0008', '\u000B', '\u000E', '\u000F', '\u0010', '\u0011', '\u0012', '\u0013', '\u0014',
                                      '\u0015', '\u0016', '\u0017', '\u0018', '\u0019', '\u001A', '\u001B', '\u001C', '\u001D',
                                      '\u001E', '\u001F']),
            min_size=0,
            max_size=20,
        )

    def escape_json_string(s: str) -> str:
        # Escape backslash and quote
        s = s.replace('\\', '\\\\').replace('"', '\\"')
        # Escape control chars (none should be present due to generation)
        # Escape other special chars with \b, \f, \n, \r, \t if present
        s = s.replace('\b', '\\b').replace('\f', '\\f').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        # For safety, escape any remaining control chars as \uXXXX
        def esc_char(c):
            if ord(c) < 0x20:
                return '\\u%04x' % ord(c)
            else:
                return c
        s = ''.join(esc_char(c) for c in s)
        return '"' + s + '"'

    json_string_strategy = json_string().map(escape_json_string)

    # NUMBER strategy: produce JSON numbers as strings
    # We'll generate floats and ints, then convert to JSON number strings
    def json_number():
        # Generate floats and ints in reasonable range
        # Use floats with limited decimal places and exponents to keep size bounded
        # Also generate ints
        int_str = st.integers(min_value=-10**6, max_value=10**6).map(str)
        float_str = st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ).map(lambda f: format(f, '.6g'))  # 6 significant digits max
        # Combine int and float strategies
        return st.one_of(int_str, float_str)

    json_number_strategy = json_number()

    # Forward declaration for recursive structures
    # We'll use st.recursive to build nested objects and arrays

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string_strategy,
        json_number_strategy,
        json_true,
        json_false,
        json_null,
    )

    # Recursive JSON value strategy
    def json_value():
        # Compose object and array strategies recursively
        # Use st.recursive to keep size bounded
        # Objects: { pair (, pair)* } or {}
        # Arrays: [ value (, value)* ] or []

        # Pair: STRING : value
        # We'll generate pairs as '"key":value' strings

        # Keys are JSON strings (reuse json_string_strategy)
        pair_strategy = st.tuples(json_string_strategy, json_value()).map(
            lambda kv: f"{kv[0]}:{kv[1]}"
        )

        obj_strategy = st.one_of(
            st.just("{}"),
            st.lists(pair_strategy, min_size=1, max_size=5).map(
                lambda pairs: "{" + ",".join(pairs) + "}"
            ),
        )

        arr_strategy = st.one_of(
            st.just("[]"),
            st.lists(json_value(), min_size=1, max_size=5).map(
                lambda values: "[" + ",".join(values) + "]"
            ),
        )

        return st.one_of(base_values, obj_strategy, arr_strategy)

    # Use st.recursive to define json_value with bounded recursion depth
    json_value_strategy = st.recursive(
        base_values,
        lambda children: st.one_of(
            # object
            st.one_of(
                st.just("{}"),
                st.lists(
                    st.tuples(json_string_strategy, children),
                    min_size=1,
                    max_size=5,
                ).map(lambda pairs: "{" + ",".join(f"{k}:{v}" for k, v in pairs) + "}"),
            ),
            # array
            st.one_of(
                st.just("[]"),
                st.lists(children, min_size=1, max_size=5).map(
                    lambda values: "[" + ",".join(values) + "]"
                ),
            ),
        ),
        max_leaves=10,
    )

    # The top-level json is a value followed by EOF (no trailing data)
    json_str = draw(json_value_strategy)

    # Return bytes encoded as UTF-8
    return json_str.encode("utf-8")