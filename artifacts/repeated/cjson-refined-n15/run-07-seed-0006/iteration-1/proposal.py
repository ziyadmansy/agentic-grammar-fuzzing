from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # JSON string: use Hypothesis text with safe codepoints, escape quotes and backslashes
    def json_string():
        # SAFECODEPOINT excludes control chars and " \, so we generate text without those
        # We'll escape " and \ manually
        s = draw(st.text(
            alphabet=st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            ),
            max_size=20,
        ))
        # Escape backslashes and quotes
        s = s.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{s}"'
    json_string_st = st.deferred(lambda: st.builds(lambda s: s, st.just(json_string())))
    # We use a composite to produce strings with escapes, so we implement it inline:
    @st.composite
    def json_string(draw):
        # generate text without control chars, " or \
        text = draw(st.text(
            alphabet=st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            ),
            max_size=20,
        ))
        # escape backslash and quote
        escaped = text.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'

    # Recursive JSON values
    # We'll define a recursive strategy for JSON values
    def json_value():
        # base cases
        base = st.one_of(
            json_string(),
            json_number,
            json_null,
            json_true,
            json_false,
        )
        # recursive cases: object and array
        # limit max size to keep output bounded
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.dictionaries(
                    keys=json_string(),
                    values=children,
                    max_size=3,
                    # keys must be unique strings, so dictionary is good
                ).map(lambda d: "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"),
                # array: [ value (, value)* ] or []
                st.lists(children, max_size=3).map(lambda l: "[" + ",".join(l) + "]"),
            ),
            max_leaves=10,
        )

    result = draw(json_value())
    return result.encode("utf-8")