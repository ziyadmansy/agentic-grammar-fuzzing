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
    # STRING: roughly valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then JSON-encode them to ensure correctness.
    # But since we cannot import json or use eval/exec, we build strings manually.
    # We'll generate strings with safe unicode codepoints excluding control chars and quotes/backslash.
    # To keep it simple, generate ASCII printable except backslash and quote, plus some escapes.
    safe_chars = st.characters(
        blacklist_characters='"\\',
        min_codepoint=0x20,
        max_codepoint=0x7E,
    )
    # Add some escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
    # We'll generate strings with a mix of safe chars and escapes.
    def json_string():
        # Compose a string of length 0 to 20 with safe chars and escapes
        # escapes as literals: \", \\, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from([
            r'\"', r'\\', r'\b', r'\f', r'\n', r'\r', r'\t',
            # \u followed by 4 hex digits
        ])
        def unicode_escape():
            hex4 = st.text(st.characters("0123456789abcdefABCDEF"), min_size=4, max_size=4)
            return hex4.map(lambda h: r"\u" + h)
        escape_or_char = st.one_of(escapes, unicode_escape(), safe_chars.map(lambda c: c))
        return st.text(escape_or_char, min_size=0, max_size=20).map(lambda s: f'"{s}"')
    json_string = json_string()

    # Recursive JSON values: string, number, obj, arr, true, false, null
    # Use st.recursive to bound size and depth
    base = st.one_of(
        json_string,
        json_number,
        json_true,
        json_false,
        json_null,
    )

    def json_obj():
        # pair: STRING ':' value
        # We'll generate pairs as (string, value)
        # Limit number of pairs to 0..5
        def pair():
            return st.tuples(json_string, json_value).map(lambda t: f"{t[0]}:{t[1]}")
        # obj: '{' pair (',' pair)* '}' or '{}'
        return st.lists(pair(), max_size=5).map(
            lambda pairs: "{" + ",".join(pairs) + "}" if pairs else "{}"
        )

    def json_arr():
        # arr: '[' value (',' value)* ']' or '[]'
        return st.lists(json_value, max_size=5).map(
            lambda values: "[" + ",".join(values) + "]" if values else "[]"
        )

    # We need json_value for recursion, so define it as a placeholder first
    json_value = st.deferred(lambda: st.one_of(base, json_obj(), json_arr()))

    # Now we can redefine json_obj and json_arr with json_value in scope
    def json_obj():
        def pair():
            return st.tuples(json_string, json_value).map(lambda t: f"{t[0]}:{t[1]}")
        return st.lists(pair(), max_size=5).map(
            lambda pairs: "{" + ",".join(pairs) + "}" if pairs else "{}"
        )

    def json_arr():
        return st.lists(json_value, max_size=5).map(
            lambda values: "[" + ",".join(values) + "]" if values else "[]"
        )

    json_value = st.recursive(
        base,
        lambda children: st.one_of(json_obj(), json_arr()),
        max_leaves=10,
    )

    # The top-level json is a value followed by EOF (no trailing data)
    json_text = json_value

    s = draw(json_text)
    return s.encode("utf-8")