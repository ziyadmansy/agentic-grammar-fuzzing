from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # JSON string: use Hypothesis's built-in string strategy with safe codepoints
    # We must produce valid JSON strings, so we escape properly.
    # We'll generate Python strings and then json-encode them.
    # But since we can't import json, we must produce JSON string literals ourselves.

    def json_string():
        # Generate a string without control chars or quotes or backslash
        # Then escape it properly
        s = draw(st.text(
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            ),
            max_size=20,
        ))
        # Escape backslash and quotes if any (should not be present)
        # Escape control chars if any (should not be present)
        # But since we excluded them, just escape backslash and quotes if any
        # Actually, we excluded them, so just wrap in quotes
        # We must also escape backslash and quotes if present, but none present.
        # So just wrap in quotes.
        # To be safe, replace backslash and quote anyway:
        s = s.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{s}"'

    json_string_st = st.deferred(lambda: st.just(json_string()))

    # JSON number: generate numbers as strings matching the grammar
    def json_number():
        # Use floats and ints, then convert to string matching JSON number grammar
        n = draw(st.one_of(
            st.integers(min_value=-10**6, max_value=10**6),
            st.floats(allow_nan=False, allow_infinity=False, width=32),
        ))
        # Format number as JSON number string
        if isinstance(n, int):
            return str(n)
        else:
            # Format float with minimal representation
            # Use repr to get a valid JSON number representation
            s = repr(n)
            # repr may produce 'nan' or 'inf' but we disallowed those
            # repr may produce '1e-07' which is valid JSON number
            return s

    json_number_st = st.deferred(lambda: st.just(json_number()))

    # Recursive JSON value strategy
    # We use st.recursive to build nested objects and arrays

    # Forward declaration for value
    # We'll define a function returning a strategy for value

    def json_value():
        base = st.one_of(
            json_string_st,
            json_number_st,
            json_null,
            json_true,
            json_false,
        )
        # Recursive containers: object and array
        def json_object():
            # pair: STRING ':' value
            # STRING is json_string_st
            # value is json_value()
            # pairs separated by commas
            # empty object allowed
            pairs = st.dictionaries(
                keys=st.text(
                    st.characters(
                        blacklist_characters=['"', '\\', '\u0000', '\u001F'],
                        min_codepoint=0x20,
                        max_codepoint=0x10FFFF,
                    ),
                    max_size=10,
                ),
                values=json_value(),
                max_size=5,
                # keys must be strings, so we will convert keys to JSON strings
            )
            def to_json_obj(d):
                if not d:
                    return "{}"
                items = []
                for k, v in d.items():
                    # Escape key as JSON string
                    k_escaped = k.replace('\\', '\\\\').replace('"', '\\"')
                    k_json = f'"{k_escaped}"'
                    items.append(f"{k_json}:{v}")
                return "{" + ",".join(items) + "}"
            return pairs.map(to_json_obj)

        def json_array():
            # array: '[' value (',' value)* ']' or '[]'
            arr = st.lists(json_value(), max_size=5)
            def to_json_arr(lst):
                return "[" + ",".join(lst) + "]"
            return arr.map(to_json_arr)

        return st.recursive(
            base,
            lambda children: st.one_of(json_object(), json_array()),
            max_leaves=10,
        )

    val = draw(json_value())
    # val is a JSON string representing a value

    # The grammar requires json : value EOF
    # So val is the entire JSON document

    return val.encode("utf-8")