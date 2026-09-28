from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # STRING: roughly valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then JSON-encode them using repr or json.dumps
    # but since we can't import json, we'll do a simple escape for quotes and backslashes.
    def json_string(s: str) -> str:
        # Escape backslash and quote for JSON string
        s = s.replace('\\', '\\\\').replace('"', '\\"')
        # Escape control chars (U+0000 to U+001F) as \uXXXX
        def esc_char(c):
            if ord(c) < 0x20:
                return f"\\u{ord(c):04x}"
            return c
        s = "".join(esc_char(c) for c in s)
        return f'"{s}"'
    json_string_strategy = st.text(
        alphabet=st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=20,
    ).map(json_string)

    # Recursive JSON values
    # We'll use st.recursive to build obj and arr with bounded depth and size
    base = st.one_of(json_null, json_true, json_false, json_number, json_string_strategy)

    # Forward declarations for obj and arr
    # pair: STRING ':' value
    # obj: '{' pair (',' pair)* '}' | '{}'
    # arr: '[' value (',' value)* ']' | '[]'

    # To avoid infinite recursion, limit max depth and max pairs/values per container
    max_pairs = 3
    max_values = 3

    def json_pair():
        return st.tuples(json_string_strategy, value).map(lambda p: f"{p[0]}:{p[1]}")

    def json_obj():
        # empty or with pairs joined by commas
        pairs = st.lists(json_pair(), max_size=max_pairs)
        return pairs.map(lambda ps: "{" + ",".join(ps) + "}")

    def json_arr():
        values = st.lists(value, max_size=max_values)
        return values.map(lambda vs: "[" + ",".join(vs) + "]")

    # value includes base plus obj and arr
    # We define value here to use in json_pair and json_obj/arr
    # Use st.recursive to build nested structures
    value = st.deferred(lambda: st.recursive(
        base,
        lambda children: st.one_of(json_obj(), json_arr()),
        max_leaves=10,
    ))

    # Now generate a full json document: value + EOF
    json_doc = value.map(lambda s: s.encode("utf-8"))

    return draw(json_doc)