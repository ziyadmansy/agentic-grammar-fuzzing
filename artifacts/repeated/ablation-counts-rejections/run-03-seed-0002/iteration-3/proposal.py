from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # JSON strings: use Hypothesis's built-in text with safe codepoints
    # SAFECODEPOINT excludes control chars and quotes/backslash
    # We'll exclude control chars and backslash and quote explicitly
    json_string = st.text(
        alphabet=st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\b', '\\b').replace('\f', '\\f').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t').replace('"', '\\"').replace('\\', '\\\\') + '"')

    # Recursive JSON values
    # We'll define a function to build recursive JSON values with bounded depth
    def json_value():
        # base cases: string, number, true, false, null
        base = st.one_of(json_string, json_number, json_true, json_false, json_null)

        # recursive cases: object and array
        # Use st.recursive to control size and depth
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string,
                    values=children,
                    min_size=0,
                    max_size=3,
                ).map(lambda d: "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"),
                # array: [ value (, value)* ] or []
                st.lists(children, min_size=0, max_size=3).map(lambda l: "[" + ",".join(l) + "]"),
            ),
            max_leaves=10,
        )

    json_val = draw(json_value())
    return json_val.encode("utf-8")