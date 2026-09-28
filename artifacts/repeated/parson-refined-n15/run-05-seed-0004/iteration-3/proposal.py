from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly matching grammar, allowing escapes and safe codepoints
    # We'll generate Python strings and then json.dumps them to ensure correctness.
    # But since we can't import json or eval, we build strings manually.
    # Instead, generate unicode strings excluding control chars and quotes/backslash,
    # then escape backslash and quotes manually.
    def json_string():
        # safe codepoints: exclude control chars (0x00-0x1F), quote, backslash
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        )
        # generate strings of length 0..20
        s = draw(st.text(safe_chars, max_size=20))
        # escape backslash and quote if any (shouldn't be present), but just in case
        s = s.replace('\\', '\\\\').replace('"', '\\"')
        # also escape control chars if any (should not be present)
        # but since we excluded them, no need
        return f'"{s}"'

    # NUMBER: generate numbers as strings matching grammar
    def json_number():
        # generate floats and ints, then convert to string matching grammar
        # We'll generate numbers as strings directly:
        # sign optional, int part, optional frac, optional exp
        sign = draw(st.sampled_from(["", "-"]))
        int_part = draw(st.one_of(st.just("0"), st.from_regex(r"[1-9][0-9]*", fullmatch=True)))
        frac_part = draw(st.one_of(st.just(""), st.from_regex(r"\.[0-9]+", fullmatch=True)))
        exp_part = draw(st.one_of(st.just(""), st.from_regex(r"[Ee][+-]?[0-9]+", fullmatch=True)))
        return f"{sign}{int_part}{frac_part}{exp_part}"

    # Recursive JSON value generator
    # We'll use st.recursive to build nested objects and arrays, bounded in size.
    # Base cases: string, number, true, false, null
    base = st.one_of(
        st.deferred(lambda: st.just(json_string())),
        st.deferred(lambda: st.just(json_number())),
        json_null,
        json_true,
        json_false,
    )

    # Recursive containers: obj and arr
    # obj: '{' pair (',' pair)* '}' or '{}'
    # pair: STRING ':' value
    # arr: '[' value (',' value)* ']' or '[]'

    # We'll define pair as STRING ':' value string
    # For STRING in pair, reuse json_string()

    def json_pair():
        key = draw(st.just(json_string()))
        val = draw(value)
        return f"{key}:{val}"

    def json_obj():
        # empty or 1..max_pairs pairs
        max_pairs = 3
        n = draw(st.integers(min_value=0, max_value=max_pairs))
        if n == 0:
            return "{}"
        pairs = [draw(json_pair()) for _ in range(n)]
        return "{" + ",".join(pairs) + "}"

    def json_arr():
        # empty or 1..max_elements values
        max_elements = 3
        n = draw(st.integers(min_value=0, max_value=max_elements))
        if n == 0:
            return "[]"
        elements = [draw(value) for _ in range(n)]
        return "[" + ",".join(elements) + "]"

    # value is recursive: base or obj or arr
    value = st.recursive(
        base,
        lambda children: st.one_of(
            st.deferred(lambda: st.just(json_obj())),
            st.deferred(lambda: st.just(json_arr())),
        ),
        max_leaves=10,
    )

    # Draw the top-level json value and add EOF (nothing)
    result = draw(value)
    # Return bytes
    return result.encode("utf-8")