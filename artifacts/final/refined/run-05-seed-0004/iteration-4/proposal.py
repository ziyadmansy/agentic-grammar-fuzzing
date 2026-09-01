from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly matching JSON string with escapes
    # We'll generate Python strings and then JSON-encode them
    # to ensure valid escaping.
    # Use a small max size to keep output size bounded.
    json_string = st.text(
        st.characters(
            blacklist_characters=['"', '\\', '\u0000', '\u0001', '\u001F'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        max_size=15,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # NUMBER: generate numbers as strings matching the grammar
    # We'll generate floats and ints and convert to strings
    def number_to_json(n):
        # Format number to JSON number string
        # Use repr to keep exponent if any
        s = repr(n)
        # Remove trailing .0 for ints
        if s.endswith('.0'):
            s = s[:-2]
        return s

    json_number = st.one_of(
        st.integers(min_value=-10**6, max_value=10**6).map(number_to_json),
        st.floats(
            allow_nan=False,
            allow_infinity=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ).map(number_to_json),
    )

    # Forward declare value strategy for recursion
    # We'll use st.recursive to build obj and arr

    # Define value base: primitives only
    json_value_base = st.one_of(
        json_string,
        json_number,
        json_null,
        json_true,
        json_false,
    )

    # Define obj and arr recursively
    # pair: STRING ':' value
    # obj: '{' pair (',' pair)* '}' | '{}'
    # arr: '[' value (',' value)* ']' | '[]'

    # To keep recursion bounded, limit max_depth and max_size
    max_depth = 3
    max_pairs = 4
    max_arr_len = 4

    def json_obj(value_strat):
        # pair: STRING ':' value
        pair = st.tuples(json_string, value_strat).map(lambda p: p[0] + ':' + p[1])
        # list of pairs
        pairs = st.lists(pair, max_size=max_pairs)
        # map pairs to object string
        return pairs.map(
            lambda ps: '{' + (','.join(ps) if ps else '') + '}'
        )

    def json_arr(value_strat):
        # list of values
        values = st.lists(value_strat, max_size=max_arr_len)
        return values.map(
            lambda vs: '[' + (','.join(vs) if vs else '') + ']'
        )

    json_value = st.recursive(
        json_value_base,
        lambda children: st.one_of(
            json_obj(children),
            json_arr(children),
        ),
        max_leaves=50,
    )

    # Compose full json with EOF (just ensure full consumption)
    json_full = json_value

    s = draw(json_full)
    return s.encode("utf-8")