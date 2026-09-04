from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON values
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # JSON strings: use Hypothesis text with safe codepoints, escape as needed
    # We'll produce JSON string literals with proper escaping
    def json_string():
        # Use a restricted set of characters to avoid control chars
        # We'll escape quotes and backslashes manually
        text = st.text(
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            ),
            max_size=20,
        )
        def escape_json_string(s: str) -> str:
            # Escape backslash and quote
            s = s.replace('\\', '\\\\').replace('"', '\\"')
            # Also escape control chars if any (should not be present due to min_codepoint=0x20)
            return f'"{s}"'
        return text.map(escape_json_string)
    json_string = json_string()

    # Forward declaration for recursive structures
    # We'll use st.recursive to build nested arrays and objects with bounded depth and size
    base = st.one_of(json_null, json_true, json_false, json_number, json_string)

    # Recursive containers: arrays and objects
    # Arrays: [value, value, ...]
    # Objects: {"key": value, ...}
    # Keys are JSON strings (already defined)
    def json_object():
        # pair: STRING : value
        # keys: use json_string but strip quotes for keys (keys must be strings)
        keys = st.text(
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            ),
            max_size=10,
        )
        def escape_key(s: str) -> str:
            s = s.replace('\\', '\\\\').replace('"', '\\"')
            return f'"{s}"'
        key_strat = keys.map(escape_key)
        # pairs: key : value
        # We'll generate a list of pairs with max length 5 to keep size bounded
        pairs = st.lists(
            st.tuples(key_strat, generated_json_value),
            max_size=5,
            unique_by=lambda kv: kv[0],  # unique keys
        )
        return pairs.map(
            lambda kvs: "{" + ",".join(f"{k}:{v}" for k, v in kvs) + "}"
        )

    def json_array():
        # arrays of values, max length 5
        return st.lists(generated_json_value, max_size=5).map(
            lambda vs: "[" + ",".join(vs) + "]"
        )

    # We'll define generated_json_value as a recursive strategy
    # Use st.recursive with base and containers
    # Containers are arrays and objects
    # To avoid infinite recursion, limit max_leaves and max_size
    generated_json_value = st.recursive(
        base,
        lambda children: st.one_of(
            json_array(),
            json_object(),
        ),
        max_leaves=10,
    )

    # Draw a value and encode as bytes
    val = draw(generated_json_value)
    return val.encode("utf-8")