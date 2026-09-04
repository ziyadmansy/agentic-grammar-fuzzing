from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitive values
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.from_regex(
        r'-?(0|[1-9]\d*)(\.\d+)?([eE][+-]?\d+)?',
        fullmatch=True,
        max_size=20,
    )
    # STRING: produce valid JSON strings with escaped characters
    # Use a small subset of safe unicode codepoints and escapes
    # SAFECODEPOINT: ~["\\\u0000-\u001F]
    # We'll generate strings with safe unicode chars and some escapes
    def json_string_chars():
        # safe codepoints excluding control chars and " and \
        safe_char = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\b', r'\f', r'\n', r'\r', r'\t',
        ])
        # unicode escape \uXXXX with hex digits
        unicode_escape = st.builds(
            lambda h1,h2,h3,h4: r'\u' + h1 + h2 + h3 + h4,
            st.sampled_from('0123456789abcdefABCDEF'),
            st.sampled_from('0123456789abcdefABCDEF'),
            st.sampled_from('0123456789abcdefABCDEF'),
            st.sampled_from('0123456789abcdefABCDEF'),
        )
        return st.one_of(safe_char, escapes, unicode_escape)

    json_string = st.text(json_string_chars(), min_size=0, max_size=20).map(
        lambda s: '"' + s + '"'
    )

    # Compose base values
    base = st.one_of(json_string, json_number, json_null, json_true, json_false)

    # Recursive strategy for arrays and objects
    # Limit max_leaves to keep recursion and size bounded
    json_value = st.recursive(
        base,
        lambda children: st.one_of(
            # array: [value, value, ...]
            st.lists(children, min_size=0, max_size=5).map(
                lambda vs: "[" + ",".join(vs) + "]"
            ),
            # object: {"string": value, ...}
            st.dictionaries(
                json_string,
                children,
                min_size=0,
                max_size=5,
                # keys must be unique strings, no duplicates
            ).map(
                lambda d: "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"
            ),
        ),
        max_leaves=20,
    )

    # Compose full JSON with EOF (no trailing chars)
    json_text = draw(json_value)
    return json_text.encode("utf-8")