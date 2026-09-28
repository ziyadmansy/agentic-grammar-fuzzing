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
    # But since we cannot import json or eval, we approximate with a safe subset.
    # We'll generate strings without control chars and backslash or quote, plus some escapes.
    # To keep it simple, generate unicode strings without control chars or quotes/backslash.
    # Then quote them ourselves.
    def json_string():
        # safe codepoints: no control chars, no " or \
        safe_chars = (
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # generate a string of length 0..20
        s = draw(st.text(safe_chars, max_size=20))
        # escape backslash and quote if any (should be none)
        # but to be safe, replace backslash and quote with escapes
        s_escaped = (
            s.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\b", "\\b")
            .replace("\f", "\\f")
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        )
        return f'"{s_escaped}"'

    json_string_st = st.builds(json_string)

    # Forward declaration for recursive structures
    # We'll define value recursively with bounded depth
    # Use st.recursive to build obj and arr from primitives

    # primitives: string, number, true, false, null
    primitives = st.one_of(json_string_st, json_number, json_true, json_false, json_null)

    # obj and arr will be built recursively
    # pair: STRING ':' value
    def json_pair():
        key = draw(json_string_st)
        val = draw(value_st)
        return f"{key}:{val}"

    # We cannot use draw inside st.recursive, so define pair as a strategy
    pair_st = st.tuples(json_string_st, st.deferred(lambda: value_st)).map(
        lambda kv: f"{kv[0]}:{kv[1]}"
    )

    def json_obj():
        # empty or with pairs separated by commas
        # limit pairs count to 0..3 for bounded size
        pairs = draw(st.lists(pair_st, max_size=3))
        if not pairs:
            return "{}"
        else:
            return "{" + ",".join(pairs) + "}"

    def json_arr():
        # empty or with values separated by commas
        vals = draw(st.lists(value_st, max_size=3))
        if not vals:
            return "[]"
        else:
            return "[" + ",".join(vals) + "]"

    # We cannot call draw inside st.recursive, so we define value_st here with st.recursive
    # We'll define a helper function to build value_st with bounded recursion

    # To do this, define value_st outside and then assign it after defining obj and arr

    # We'll define value_st as a recursive strategy combining primitives and containers

    # Define containers as strategies that produce strings (json text)
    containers = st.deferred(lambda: st.one_of(obj_st, arr_st))

    value_st = st.recursive(
        primitives,
        lambda children: st.one_of(
            # obj: {} or {pair(,pair)*}
            st.builds(
                lambda pairs: "{" + ",".join(pairs) + "}" if pairs else "{}",
                st.lists(
                    st.tuples(json_string_st, children).map(lambda kv: f"{kv[0]}:{kv[1]}"),
                    max_size=3,
                ),
            ),
            # arr: [] or [value(,value)*]
            st.builds(
                lambda vals: "[" + ",".join(vals) + "]" if vals else "[]",
                st.lists(children, max_size=3),
            ),
        ),
        max_leaves=10,
    )

    # Draw the final json text
    json_text = draw(value_st)
    return json_text.encode("utf-8")