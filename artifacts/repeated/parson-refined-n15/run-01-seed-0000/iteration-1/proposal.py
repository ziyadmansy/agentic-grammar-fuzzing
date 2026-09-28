from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # STRING: simplified safe string with escapes
    def json_string():
        # Generate strings with safe codepoints and some escapes
        # Use a small subset of escapes to keep near-valid
        escapes = st.sampled_from(['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t'])
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Mix safe chars and escapes
        str_chars = st.lists(st.one_of(safe_char, escapes), max_size=10)
        return str_chars.map(lambda cs: '"' + ''.join(cs) + '"')

    json_string = json_string()

    # Recursive definition for value
    def json_value():
        # Forward declaration to allow recursion
        return st.deferred(lambda: json_value_inner())

    def json_value_inner():
        # Compose all value options
        base = st.one_of(
            json_string,
            json_number,
            json_true,
            json_false,
            json_null,
        )
        # Recursive containers: object and array
        # Use bounded recursion to keep size small
        return st.recursive(
            base,
            lambda children: st.one_of(
                json_object(children),
                json_array(children),
            ),
            max_leaves=5,
        )

    # Object: '{' pair (',' pair)* '}' or '{}'
    def json_object(value_strat):
        # pair: STRING ':' value
        pair = st.tuples(json_string, value_strat).map(lambda p: f"{p[0]}:{p[1]}")
        # zero or more pairs separated by commas
        pairs = st.lists(pair, max_size=3)
        return pairs.map(lambda ps: "{" + (",".join(ps)) + "}")

    # Array: '[' value (',' value)* ']' or '[]'
    def json_array(value_strat):
        values = st.lists(value_strat, max_size=3)
        return values.map(lambda vs: "[" + (",".join(vs)) + "]")

    # Generate the full JSON text and append EOF implicitly
    json_text = json_value_inner()

    s = draw(json_text)
    return s.encode("utf-8")