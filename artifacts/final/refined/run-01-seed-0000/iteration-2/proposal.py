from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # JSON strings: use Hypothesis text with safe codepoints, escape as needed
    # SAFECODEPOINT excludes control chars and " \, so we generate text without those
    def json_string():
        # Generate text excluding control chars and " and \
        # Control chars: \u0000-\u001F
        # Exclude " and \
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Limit length to keep size bounded
        return st.text(safe_chars, min_size=0, max_size=20).map(
            lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
        )
    json_str = json_string()

    # Recursive JSON value strategy
    # We build from primitives and recurse into arrays and objects
    # Limit max_leaves to keep recursion bounded

    # Forward declaration for recursive use
    def json_value():
        return st.deferred(lambda: json_value_strategy)

    # Object: { pair (, pair)* } or {}
    # pair: STRING : value
    def json_pair():
        return st.tuples(json_str, json_value()).map(lambda p: f"{p[0]}:{p[1]}")

    json_obj = st.lists(json_pair(), min_size=0, max_size=5).map(
        lambda pairs: "{" + ",".join(pairs) + "}"
    )

    # Array: [ value (, value)* ] or []
    json_arr = st.lists(json_value(), min_size=0, max_size=5).map(
        lambda values: "[" + ",".join(values) + "]"
    )

    json_value_strategy = st.recursive(
        st.one_of(json_null, json_true, json_false, json_number, json_str),
        lambda children: st.one_of(json_obj, json_arr),
        max_leaves=10,
    )

    result = draw(json_value_strategy)
    return result.encode("utf-8")