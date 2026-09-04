from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives as Python objects
    json_null = st.just(None)
    json_bool = st.booleans()
    json_number = st.floats(allow_infinity=False, allow_nan=False).map(lambda f: int(f) if f.is_integer() else f)
    # JSON strings: safe unicode codepoints excluding control chars and quotes/backslash
    json_string = st.text(
        alphabet=st.characters(
            blacklist_characters=['"', '\\'],
            min_codepoint=0x20,
            max_codepoint=0x10FFFF,
        ),
        min_size=0,
        max_size=20,
    )

    # Recursive JSON values
    json_value = st.deferred(lambda: json_)

    # JSON arrays
    json_array = st.lists(json_value, max_size=5)

    # JSON objects: keys are strings, values are json_value
    json_object = st.dictionaries(json_string, json_value, max_size=5)

    # Compose all JSON values
    json_ = st.one_of(
        json_null,
        json_bool,
        json_number,
        json_string,
        json_array,
        json_object,
    )

    # Draw a JSON value
    value = draw(json_)

    # Serialize to JSON bytes with minimal whitespace
    import json as pyjson
    s = pyjson.dumps(value, separators=(',', ':'))
    return s.encode('utf-8')