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
        max_size=20,
    )
    # STRING with escapes and safe codepoints
    # We'll generate strings with safe unicode codepoints and some escapes
    # To keep it simple, generate Python strings and then json-encode them
    # but since we can't import json, we do minimal escaping here.
    def json_string():
        # safe characters excluding control chars and quotes/backslash
        safe_chars = (
            st.characters(
                blacklist_characters='"\\',
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # escape sequences: \", \\, \b, \f, \n, \r, \t, \uXXXX
        escapes = st.sampled_from(
            ['\\"', '\\\\', '\\b', '\\f', '\\n', '\\r', '\\t']
        )
        # unicode escape: \uXXXX
        def unicode_escape():
            hex_digit = st.sampled_from("0123456789abcdefABCDEF")
            return st.tuples(hex_digit, hex_digit, hex_digit, hex_digit).map(
                lambda t: "\\u" + "".join(t)
            )
        # build string pieces: either safe char or escape or unicode escape
        piece = st.one_of(
            safe_chars.map(lambda c: c),
            escapes,
            unicode_escape(),
        )
        # generate list of pieces, join and wrap in quotes
        pieces = st.lists(piece, max_size=20).map("".join)
        return pieces.map(lambda s: f'"{s}"')

    json_string_st = json_string()

    # Recursive value strategy
    # We'll limit recursion depth and size to keep bounded outputs
    def json_value():
        # base cases: string, number, true, false, null
        base = st.one_of(
            json_string_st,
            json_number,
            json_true,
            json_false,
            json_null,
        )
        # recursive cases: obj and arr
        # obj: {} or {"pair", ...}
        # pair: STRING : value
        # arr: [] or [value, ...]
        # Use st.recursive to build these
        def obj_strategy():
            # pair: STRING : value
            pair = st.tuples(json_string_st, json_value()).map(
                lambda p: f"{p[0]}:{p[1]}"
            )
            # object with pairs separated by commas or empty
            return st.one_of(
                st.just("{}"),
                st.lists(pair, max_size=5).map(lambda pairs: "{" + ",".join(pairs) + "}"),
            )

        def arr_strategy():
            return st.one_of(
                st.just("[]"),
                st.lists(json_value(), max_size=5).map(
                    lambda values: "[" + ",".join(values) + "]"
                ),
            )

        return st.deferred(
            lambda: st.one_of(
                base,
                obj_strategy(),
                arr_strategy(),
            )
        )

    # Use st.recursive to limit depth and size
    value_strategy = st.recursive(
        st.one_of(json_string_st, json_number, json_true, json_false, json_null),
        lambda children: st.one_of(
            # object
            st.lists(
                st.tuples(json_string_st, children), max_size=3
            ).map(lambda pairs: "{" + ",".join(f"{k}:{v}" for k, v in pairs) + "}"),
            # array
            st.lists(children, max_size=3).map(lambda values: "[" + ",".join(values) + "]"),
        ),
        max_leaves=10,
    )

    # Compose full json with EOF (just ensure full string)
    json_text = draw(value_strategy)
    return json_text.encode("utf-8")