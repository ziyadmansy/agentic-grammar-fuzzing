from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.from_regex(r'-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?', fullmatch=True)
    # STRING: roughly matching the grammar, allowing escapes and safe codepoints
    # We'll generate Python strings and then encode as JSON strings using repr-like escaping
    # but Hypothesis has a built-in json string strategy:
    json_string = st.text(
        alphabet=(
            # safe codepoints: all except control chars and " and \
            # control chars: \u0000-\u001F
            # exclude " and \
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        ),
        min_size=0,
        max_size=20,
    ).map(lambda s: '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"')

    # Recursive JSON values: string, number, obj, arr, true, false, null
    # We'll define a recursive strategy with bounded depth and size

    # Forward declaration for recursion
    def json_value():
        return st.deferred(lambda: json_value_strategy)

    # Object: '{' pair (',' pair)* '}' or '{}'
    # pair: STRING ':' value
    # We'll limit number of pairs to keep size bounded
    json_pair = st.tuples(json_string, json_value())
    json_obj = st.dictionaries(
        keys=json_string,
        values=json_value(),
        min_size=0,
        max_size=3,
    ).map(
        lambda d: (
            '{' + ','.join(f'{k}:{v}' for k, v in d.items()) + '}'
            if d else '{}'
        )
    )

    # Array: '[' value (',' value)* ']' or '[]'
    json_arr = st.lists(json_value(), min_size=0, max_size=3).map(
        lambda l: '[' + ','.join(l) + ']' if l else '[]'
    )

    json_value_strategy = st.recursive(
        base=st.one_of(json_string, json_number, json_true, json_false, json_null),
        extend=lambda children: st.one_of(json_obj, json_arr),
        max_leaves=10,
    )

    # Draw a full JSON value and append EOF (implicit)
    result = draw(json_value_strategy)
    return result.encode('utf-8')