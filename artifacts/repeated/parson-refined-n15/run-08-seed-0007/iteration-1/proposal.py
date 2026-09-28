from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: roughly follow grammar, but simplified for fuzzing
    # Use Hypothesis's built-in json string strategy, but restrict control chars
    json_string = st.text(
        alphabet=(
            # safe codepoints excluding control chars and quotes/backslash
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # NUMBER strategy: generate valid JSON numbers as strings
    # Use floats and ints converted to strings, with some control on format
    def number_to_json(n):
        # Format int or float as JSON number string
        if isinstance(n, int):
            return str(n)
        else:
            # Use repr to get a JSON-compatible float string
            # but avoid scientific notation for simplicity
            s = repr(n)
            if 'e' in s or 'E' in s:
                # convert scientific notation to decimal if possible
                try:
                    f = float(s)
                    s = format(f, 'f').rstrip('0').rstrip('.')
                    if s == '':
                        s = '0'
                except Exception:
                    pass
            return s

    json_number = st.one_of(
        st.integers(min_value=-1_000_000, max_value=1_000_000),
        st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ),
    ).map(number_to_json)

    # Recursive JSON value strategy
    # Use st.recursive to build nested arrays and objects with bounded depth and size
    base = st.one_of(json_string, json_number, json_null, json_true, json_false)

    # Forward declarations for recursive structures
    # obj: '{' pair (',' pair)* '}' | '{}'
    # pair: STRING ':' value
    # arr: '[' value (',' value)* ']' | '[]'

    def json_obj():
        # pair: STRING ':' value
        pair = st.tuples(json_string, value).map(lambda p: p[0] + ':' + p[1])
        # object with 0 to 5 pairs
        return st.builds(
            lambda pairs: '{' + ','.join(pairs) + '}',
            st.lists(pair, max_size=5),
        )

    def json_arr():
        # array with 0 to 5 values
        return st.builds(
            lambda values: '[' + ','.join(values) + ']',
            st.lists(value, max_size=5),
        )

    # Compose value recursively
    value = st.recursive(
        base,
        lambda children: st.one_of(json_obj(), json_arr()),
        max_leaves=10,
    )

    # Compose full JSON: value + EOF
    json_text = value

    s = draw(json_text)
    return s.encode("utf-8")