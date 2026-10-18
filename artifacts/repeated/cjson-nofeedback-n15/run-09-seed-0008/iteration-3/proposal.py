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
        # safe codepoints: no control chars, no " or \
        safe_chars = st.characters(
            blacklist_characters=['\\', '"'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # include some escapes by mixing in escaped sequences
        escapes = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # build a string of length 0..20 with mostly safe chars and some escapes
        pieces = st.lists(
            st.one_of(
                safe_chars.map(lambda c: c),
                escapes,
            ),
            min_size=0,
            max_size=20,
        )
        def to_json_string(pieces):
            # pieces is a list of str, some are single chars, some are escapes like \n
            # join and wrap in quotes
            return '"' + ''.join(pieces) + '"'
        return pieces.map(to_json_string)

    json_string_st = json_string()

    # NUMBER strategy: produce valid JSON numbers as strings
    # Use Hypothesis floats converted to JSON number strings with constraints
    def json_number():
        # Generate floats or ints within reasonable bounds
        # We'll generate strings matching the grammar: '-'? INT ('.' [0-9]+)? EXP?
        # Use floats but format carefully
        def float_to_json_number(f):
            # Format float to JSON number string without trailing .0 if possible
            # Use repr to get a compact representation
            s = repr(f)
            # repr can produce inf/nan, reject those
            if s in ('inf', '-inf', 'nan', '-nan'):
                return None
            # JSON numbers cannot have leading zeros except zero itself
            # repr floats don't have leading zeros
            return s

        floats = st.floats(
            allow_infinity=False,
            allow_nan=False,
            width=32,
            min_value=-1e10,
            max_value=1e10,
        )
        # Also generate ints as strings
        ints = st.integers(min_value=-10**10, max_value=10**10).map(str)

        # Combine ints and floats, filter out None
        combined = st.one_of(
            floats.map(float_to_json_number).filter(lambda x: x is not None),
            ints,
        )
        return combined

    json_number_st = json_number()

    # Recursive JSON value strategy
    # We'll use st.recursive to build nested arrays and objects
    # Limit max depth and size to keep examples bounded

    # Base values: string, number, true, false, null
    base = st.one_of(
        json_string_st,
        json_number_st,
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: arrays and objects
    # Arrays: '[' value (',' value)* ']' or '[]'
    # Objects: '{' pair (',' pair)* '}' or '{}'
    # pair: STRING ':' value

    # We define a helper for pairs
    @st.composite
    def json_pair(draw):
        key = draw(json_string_st)
        val = draw(value)
        return f"{key}:{val}"

    # We define arrays and objects using recursive strategy
    def arrays_and_objects(children):
        # arrays
        arrays = st.lists(children, max_size=3).map(
            lambda vs: "[" + ",".join(vs) + "]"
        )
        # objects
        pairs = st.lists(
            st.tuples(json_string_st, children),
            max_size=3,
        ).map(
            lambda kvs: "{" + ",".join(f"{k}:{v}" for k, v in kvs) + "}"
        )
        return st.one_of(arrays, pairs)

    # Compose the recursive value strategy
    value = st.recursive(
        base,
        arrays_and_objects,
        max_leaves=10,
    )

    # Compose the full JSON text: value + EOF
    json_text = value.map(lambda s: s)

    s = draw(json_text)
    return s.encode("utf-8")