from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    json_string = st.text(
        alphabet=(
            # SAFECODEPOINT: all Unicode codepoints except control chars and " \ 
            # We'll exclude control chars (U+0000-U+001F), double quote, and backslash
            # Hypothesis text default includes all Unicode, so we filter here
            # We'll just use a safe subset: printable ASCII except " and \
            # ASCII 0x20-0x21, 0x23-0x5B, 0x5D-0x7E
            # i.e. space, !, #..[, ]..~
            # This avoids needing to escape anything except quotes and backslash
            [chr(c) for c in range(0x20, 0x7F) if c not in (0x22, 0x5C)]
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # Recursive JSON value strategy
    # Use st.recursive to build nested objects and arrays
    base = st.one_of(json_null, json_true, json_false, json_number, json_string)

    # To keep size bounded, limit max_leaves and max_depth
    def json_obj():
        # pair: STRING ':' value
        # STRING is json_string without quotes for key
        key = st.text(
            alphabet=[chr(c) for c in range(0x20, 0x7F) if c not in (0x22, 0x5C)],
            min_size=1,
            max_size=10,
        )
        # keys must be quoted strings in JSON, so quote and escape
        key_quoted = key.map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')
        # pair: key_quoted + ':' + value
        return st.tuples(key_quoted, json_value).map(lambda kv: kv[0] + ":" + kv[1])

    def json_arr():
        # array of values
        return st.lists(json_value, max_size=5).map(lambda vs: "[" + ",".join(vs) + "]")

    def json_obj_full():
        # object with 0 to 5 pairs
        return st.lists(json_obj(), max_size=5).map(
            lambda pairs: "{" + ",".join(pairs) + "}" if pairs else "{}"
        )

    json_value = st.recursive(
        base,
        lambda children: st.one_of(json_obj_full(), json_arr()),
        max_leaves=20,
    )

    # Draw a JSON string and encode as bytes
    s = draw(json_value)
    return s.encode("utf-8")