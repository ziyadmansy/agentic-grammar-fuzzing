from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then dump them with json.dumps to ensure correctness.
    # But since we cannot import json or exec, we build a safe string strategy manually.
    # We'll generate strings without control chars except those escaped.
    # To keep it simple, generate unicode strings excluding control chars and quotes/backslash.
    safe_char = st.characters(
        blacklist_characters=['"', '\\'],
        blacklist_categories=('Cc',)  # control chars
    )
    json_string = st.text(safe_char, max_size=20).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # NUMBER strategy: generate numbers as strings matching the grammar
    # We'll generate floats and ints and convert to strings
    def number_to_str(n):
        # Format number to JSON number string without trailing .0 if int
        if isinstance(n, int):
            return str(n)
        else:
            # Use repr to get scientific notation if needed
            return repr(n)

    json_number = st.one_of(
        st.integers(min_value=-10**6, max_value=10**6).map(str),
        st.floats(allow_nan=False, allow_infinity=False, width=32).map(number_to_str)
    )

    # Recursive JSON value strategy
    # We'll use st.recursive with a max depth to avoid recursion errors
    # Base: primitives (string, number, true, false, null)
    base = st.one_of(json_string, json_number, json_true, json_false, json_null)

    # Recursive containers: arrays and objects
    # Arrays: [value, ...]
    # Objects: {"string": value, ...}

    # To keep output size bounded, limit max size of arrays and objects
    max_container_size = 5

    def json_object():
        # pairs: STRING : value
        # STRING keys are json_string without quotes (strip quotes)
        key_str = st.text(safe_char, max_size=10)
        # Compose pairs as '"key":value'
        return st.dictionaries(
            keys=key_str,
            values=values,
            max_size=max_container_size,
            # keys must be unique, so dictionary is good
        ).map(
            lambda d: (
                "{" +
                ",".join(
                    f'"{k.replace("\\", "\\\\").replace("\"", "\\\"")}":{v}'
                    for k, v in d.items()
                ) +
                "}"
            )
        )

    def json_array():
        return st.lists(values, max_size=max_container_size).map(
            lambda vs: "[" + ",".join(vs) + "]"
        )

    values = st.deferred(lambda: st.recursive(
        base,
        lambda children: st.one_of(json_array(), json_object()),
        max_leaves=20,
    ))

    # Draw a value and encode as bytes
    s = draw(values)
    return s.encode("utf-8")