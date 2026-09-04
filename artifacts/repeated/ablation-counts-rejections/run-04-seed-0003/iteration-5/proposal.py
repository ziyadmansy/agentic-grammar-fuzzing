from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes
    # Use st.text with safe characters and escapes
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        safe_chars = st.characters(
            blacklist_characters=['"', '\\'],
            blacklist_categories=('Cc',)  # control chars
        )
        # We allow some escapes by including backslash sequences explicitly
        # but for simplicity, generate safe unicode strings and then escape them
        # Hypothesis provides st.from_regex but here we do manual escaping
        # We'll generate a Python string and then json.dumps it to get a valid JSON string
        import json as _json
        @st.composite
        def _json_str(draw):
            s = draw(st.text(safe_chars, max_size=20))
            return _json.dumps(s)
        return _json_str()

    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: str(f))

    # Recursive strategy for JSON values
    # Use st.recursive with base cases and containers

    base = st.one_of(
        json_null,
        json_true,
        json_false,
        json_number,
        json_string(),
    )

    # Containers: arrays and objects
    # Arrays: [value, value, ...]
    # Objects: {"string": value, ...}

    def json_array(children):
        return st.lists(children, max_size=3).map(
            lambda vs: "[" + ",".join(vs) + "]"
        )

    def json_object(children):
        # keys are strings
        return st.dictionaries(
            keys=json_string(),
            values=children,
            max_size=3,
            # keys are already quoted strings, so no extra quotes needed
        ).map(
            lambda d: "{" + ",".join(f"{k}:{v}" for k, v in d.items()) + "}"
        )

    json_value = st.recursive(
        base,
        lambda children: st.one_of(
            json_array(children),
            json_object(children),
        ),
        max_leaves=10,
    )

    s = draw(json_value)
    return s.encode("utf-8")