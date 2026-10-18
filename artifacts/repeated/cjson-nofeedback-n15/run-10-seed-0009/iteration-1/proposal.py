from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.from_regex(
        r"-?(0|[1-9]\d*)(\.\d+)?([eE][+-]?\d+)?",
        fullmatch=True,
    )
    # STRING: roughly matching the grammar, allowing escapes and safe codepoints
    # We'll generate strings and then escape them properly.
    def json_string():
        # We generate unicode strings excluding control chars and quotes/backslash
        # Then escape them as needed.
        # To keep it simple, generate strings of safe codepoints and some escapes.
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Also allow some escaped sequences
        escape_sequences = st.sampled_from(['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t'])
        # Compose a string with a mix of safe chars and escape sequences
        # To keep it simple, generate a list of either safe chars or escape sequences
        pieces = st.lists(
            st.one_of(
                safe_chars.map(lambda c: c),
                escape_sequences,
            ),
            min_size=0,
            max_size=10,
        )
        def assemble(pieces):
            s = ""
            for p in pieces:
                if len(p) == 1:
                    s += p
                else:
                    s += p
            return '"' + s + '"'
        return pieces.map(assemble)

    json_string_st = json_string()

    # Recursive definition for arrays and objects
    # We'll use st.recursive to keep size bounded

    # Forward declaration of value strategy
    # We'll define it below with recursion

    # Base values for recursion
    base = st.one_of(
        json_string_st,
        json_number,
        json_null,
        json_true,
        json_false,
    )

    # Recursive containers
    def extend(value):
        # pair: STRING ':' value
        pair = st.tuples(json_string_st, value).map(lambda t: t[0] + ":" + t[1])
        obj = st.one_of(
            st.just("{}"),
            st.lists(pair, min_size=1, max_size=5).map(lambda pairs: "{" + ",".join(pairs) + "}"),
        )
        arr = st.one_of(
            st.just("[]"),
            st.lists(value, min_size=1, max_size=5).map(lambda vs: "[" + ",".join(vs) + "]"),
        )
        return st.one_of(obj, arr)

    value = st.recursive(base, extend, max_leaves=10)

    # Compose full JSON with EOF
    json_full = value.map(lambda s: s)

    s = draw(json_full)
    return s.encode("utf-8")