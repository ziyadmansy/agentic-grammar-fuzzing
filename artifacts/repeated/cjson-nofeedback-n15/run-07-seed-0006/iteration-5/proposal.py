from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode them as JSON strings
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        # We'll allow some escapes as well
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # To include escapes, we can randomly insert them
        # But for simplicity, generate unicode strings and rely on json.dumps to escape
        # However, we cannot import json, so we manually escape minimal set
        # Instead, generate strings without control chars and quotes/backslash
        return st.text(safe_chars, min_size=0, max_size=10)

    # NUMBER strategy: produce valid JSON numbers as strings
    def json_number():
        # Compose numbers as strings matching grammar
        # Use floats and ints converted to strings
        # To keep it simple, generate floats and ints and convert to strings
        # But we cannot import json or repr, so build strings manually
        # Use Hypothesis floats and ints, then format as JSON number strings
        # We'll generate strings matching the NUMBER regex:
        # '-'? INT ('.' [0-9]+)? EXP?
        # We'll build this from parts:
        sign = st.sampled_from(["", "-"])
        int_part = st.one_of(st.just("0"), st.text("123456789", min_size=1, max_size=1) + st.text("0123456789", max_size=5))
        frac_part = st.one_of(st.just(""), st.builds(lambda s: "." + s, st.text("0123456789", min_size=1, max_size=5)))
        exp_part = st.one_of(
            st.just(""),
            st.builds(
                lambda e, s, d: e + s + d,
                st.sampled_from(["e", "E"]),
                st.sampled_from(["", "+", "-"]),
                st.text("0123456789", min_size=1, max_size=3),
            ),
        )
        return st.builds(lambda sg, i, f, e: sg + i + f + e, sign, int_part, frac_part, exp_part)

    # Recursive value strategy
    def json_value():
        # Use recursive to build nested objects and arrays
        base = st.one_of(
            json_string().map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'),
            json_number(),
            json_null,
            json_true,
            json_false,
        )

        # Recursive containers
        def extend_children(children):
            # children is a strategy for values
            # obj: '{' pair (',' pair)* '}' | '{}'
            # pair: STRING ':' value
            pair = st.tuples(
                json_string().map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'),
                children,
            ).map(lambda t: t[0] + ":" + t[1])

            obj = st.one_of(
                st.just("{}"),
                st.lists(pair, min_size=1, max_size=3).map(lambda pairs: "{" + ",".join(pairs) + "}"),
            )

            # arr: '[' value (',' value)* ']' | '[]'
            arr = st.one_of(
                st.just("[]"),
                st.lists(children, min_size=1, max_size=3).map(lambda vals: "[" + ",".join(vals) + "]"),
            )

            return st.one_of(base, obj, arr)

        return st.recursive(base, extend_children, max_leaves=10)

    val = draw(json_value())
    return val.encode("utf-8")