from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(str)
    # JSON strings: use Hypothesis text with safe codepoints, escape quotes and backslashes
    def json_string():
        # SAFECODEPOINT excludes control chars and " \, so we generate text without those
        # We'll escape " and \ manually
        def escape_json_string(s: str) -> str:
            # Escape backslash and quote
            s = s.replace("\\", "\\\\").replace('"', '\\"')
            # Also escape control characters (U+0000 to U+001F)
            def esc_char(c):
                if ord(c) < 0x20:
                    return "\\u%04x" % ord(c)
                return c
            s = "".join(esc_char(c) for c in s)
            return f'"{s}"'
        return st.text(
            alphabet=st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            ),
            min_size=0,
            max_size=20,
        ).map(escape_json_string)

    json_string_strat = json_string()

    # Recursive JSON values: obj and arr
    # We'll use st.recursive to keep recursion bounded

    # Forward declaration for value
    # We'll define value as a recursive strategy

    # Define obj and arr later using value

    # Helper to build obj and arr from value
    def json_obj(value):
        # pair := STRING ':' value
        pair = st.tuples(json_string_strat, value).map(lambda p: f"{p[0]}:{p[1]}")
        # zero or more pairs separated by commas
        pairs = st.lists(pair, max_size=5)
        return pairs.map(lambda ps: "{" + (",".join(ps) if ps else "") + "}")

    def json_arr(value):
        # zero or more values separated by commas
        vals = st.lists(value, max_size=5)
        return vals.map(lambda vs: "[" + (",".join(vs) if vs else "") + "]")

    # Compose value recursively
    base = st.one_of(
        json_string_strat,
        json_number,
        json_true,
        json_false,
        json_null,
    )

    # Use recursive to add obj and arr
    value = st.recursive(
        base,
        lambda children: st.one_of(
            json_obj(children),
            json_arr(children),
        ),
        max_leaves=10,
    )

    # Compose full json: value + EOF (implicit)
    json_text = value

    s = draw(json_text)
    return s.encode("utf-8")