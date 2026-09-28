from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.from_regex(
        r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?",
        fullmatch=True,
    )
    # STRING: simplified safe string with escapes and unicode escapes
    # We'll generate Python strings and then dump them with json.dumps to ensure valid escapes
    # but since we cannot use json.dumps (no imports except hypothesis),
    # we approximate by generating strings with safe characters and some escapes.
    # We'll generate strings with safe codepoints plus some escapes.
    def json_string():
        # Characters allowed inside string: SAFECODEPOINT or escapes
        # SAFECODEPOINT excludes control chars and " and \
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        # We'll generate strings with a mix of safe chars and some escapes
        # For simplicity, generate strings of length 0 to 20 with safe chars and some escapes
        # We'll generate a Python string and then manually escape it.
        # But since we cannot do that easily, we generate strings with safe chars only,
        # plus some \uXXXX escapes as literal substrings.
        # We'll generate a list of either safe chars or unicode escape sequences.
        def one_char():
            # 80% safe char, 20% unicode escape
            return draw(
                st.one_of(
                    safe_chars,
                    st.text(
                        alphabet="\\u" + "0123456789abcdefABCDEF",
                        min_size=6,
                        max_size=6,
                    ).filter(
                        lambda s: s.startswith("\\u")
                        and all(c in "0123456789abcdefABCDEF" for c in s[2:])
                    ),
                )
            )

        length = draw(st.integers(min_value=0, max_value=20))
        chars = [one_char() for _ in range(length)]
        s = "".join(chars)
        # Wrap in quotes
        return f'"{s}"'

    json_string_st = st.deferred(json_string)

    # Recursive value strategy
    # We use st.recursive to build obj and arr with bounded depth
    base = st.one_of(
        json_string_st,
        json_number,
        json_true,
        json_false,
        json_null,
    )

    # pair: STRING ':' value
    @st.composite
    def pair(draw):
        key = draw(json_string_st)
        val = draw(value)
        return f"{key}:{val}"

    # obj: '{' pair (',' pair)* '}' | '{}'
    @st.composite
    def obj(draw):
        # limit number of pairs to keep size bounded
        n = draw(st.integers(min_value=0, max_value=3))
        if n == 0:
            return "{}"
        pairs = [draw(pair) for _ in range(n)]
        return "{" + ",".join(pairs) + "}"

    # arr: '[' value (',' value)* ']' | '[]'
    @st.composite
    def arr(draw):
        n = draw(st.integers(min_value=0, max_value=3))
        if n == 0:
            return "[]"
        vals = [draw(value) for _ in range(n)]
        return "[" + ",".join(vals) + "]"

    # value: STRING | NUMBER | obj | arr | true | false | null
    # We define value as recursive strategy
    value = st.recursive(
        base,
        lambda children: st.one_of(obj(), arr()),
        max_leaves=10,
    )

    # Draw a full json value and append EOF (implicit)
    result = draw(value)
    return result.encode("utf-8")