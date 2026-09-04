from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly matching grammar, allowing escapes and safe codepoints
    # We'll simplify escapes to common ones and unicode escapes
    def json_string():
        # Characters allowed inside string: safe codepoints or escapes
        # We'll generate Python strings and then json-encode them
        # to produce valid JSON strings.
        # Use st.text with safe characters and some escapes.
        # To keep it simple, generate unicode strings with some control chars replaced by escapes.
        # Hypothesis has a built-in json string strategy:
        # but we want to control escaping to some extent.
        # We'll use st.text with min_size=0 max_size=20, excluding control chars except \n, \t, etc.
        # Then encode with json.dumps to get a valid JSON string.
        import json
        s = draw(st.text(
            st.characters(
                blacklist_characters=['"', '\\', '\u0000', '\u0001', '\u0002', '\u0003', '\u0004',
                                      '\u0005', '\u0006', '\u0007', '\u0008', '\u000b', '\u000c',
                                      '\u000e', '\u000f', '\u0010', '\u0011', '\u0012', '\u0013',
                                      '\u0014', '\u0015', '\u0016', '\u0017', '\u0018', '\u0019',
                                      '\u001a', '\u001b', '\u001c', '\u001d', '\u001e', '\u001f'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
                whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs', 'Po', 'Ps', 'Pe', 'Sm', 'Sc', 'Sk', 'So')
            ),
            min_size=0,
            max_size=20
        ))
        # json.dumps returns a JSON string with quotes and escapes
        return json.dumps(s)

    json_string_st = st.deferred(json_string)

    # NUMBER: use hypothesis floats and ints, then convert to JSON number strings
    def json_number():
        # Generate int or float, then convert to string without quotes
        # Use floats with finite values only
        n = draw(st.one_of(
            st.integers(min_value=-(10**9), max_value=10**9),
            st.floats(allow_nan=False, allow_infinity=False, width=32)
        ))
        # Format number as JSON number string
        # Use repr for floats to get compact form
        if isinstance(n, int):
            return str(n)
        else:
            # Format float to JSON number string
            # Use repr but ensure decimal point or exponent present
            s = repr(n)
            # repr may produce '1.0' or '1e-5' which is valid JSON number
            return s

    json_number_st = st.deferred(json_number)

    # Forward declare value strategy for recursion
    # We'll build it with st.recursive

    # Compose obj and arr after value is defined
    def json_obj(value_st):
        # pair: STRING ':' value
        # Generate dict with string keys and value_st values
        # Limit size to keep bounded
        d = draw(st.dictionaries(
            keys=st.text(min_size=1, max_size=10, alphabet=st.characters(
                blacklist_characters=['"', '\\', '\u0000', '\u0001', '\u0002', '\u0003', '\u0004',
                                      '\u0005', '\u0006', '\u0007', '\u0008', '\u000b', '\u000c',
                                      '\u000e', '\u000f', '\u0010', '\u0011', '\u0012', '\u0013',
                                      '\u0014', '\u0015', '\u0016', '\u0017', '\u0018', '\u0019',
                                      '\u001a', '\u001b', '\u001c', '\u001d', '\u001e', '\u001f'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
                whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs', 'Po', 'Ps', 'Pe', 'Sm', 'Sc', 'Sk', 'So')
            )),
            min_size=0,
            max_size=5,
            unique_keys=True
        ))
        # For each key, generate a value from value_st
        obj_items = []
        for k in d.keys():
            v = draw(value_st)
            obj_items.append((k, v))
        # Build JSON object string
        import json
        # Use json.dumps to encode keys and values properly
        # Values are already JSON strings, so parse them to Python objects to re-dump
        # But values are strings representing JSON, so parse them first
        # To avoid double encoding, parse each value string to Python object
        # Then dump whole dict
        # This requires parsing each value string to Python object
        import json as pyjson
        py_obj = {}
        for k, v in obj_items:
            try:
                py_obj[k] = pyjson.loads(v)
            except Exception:
                # fallback: treat as string literal (should not happen)
                py_obj[k] = v
        return pyjson.dumps(py_obj)

    def json_arr(value_st):
        # Generate list of values from value_st
        arr_len = draw(st.integers(min_value=0, max_value=5))
        arr_items = [draw(value_st) for _ in range(arr_len)]
        # Parse each value string to Python object to re-dump as JSON array
        import json as pyjson
        py_arr = []
        for v in arr_items:
            try:
                py_arr.append(pyjson.loads(v))
            except Exception:
                py_arr.append(v)
        return pyjson.dumps(py_arr)

    # Compose value strategy recursively
    def value_strategy():
        # Base: string, number, true, false, null
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_true,
            json_false,
            json_null,
        )

        # Recursive: obj and arr
        # Use st.recursive to build nested structures
        def extend(value_st):
            return st.one_of(
                st.deferred(lambda: json_obj(value_st)),
                st.deferred(lambda: json_arr(value_st)),
            )

        return st.recursive(base, extend, max_leaves=10)

    value_st = value_strategy()

    # Generate full JSON text (value + EOF)
    # value_st produces JSON text as string, convert to bytes
    json_text = draw(value_st)
    return json_text.encode("utf-8")