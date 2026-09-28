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
    # STRING: roughly matching the grammar (no control chars, escapes allowed)
    # We'll allow simple escapes and safe codepoints
    # To keep it simple, generate Python strings and then dump with json.dumps
    # but since we can't import json, we build strings manually with escapes.
    # Instead, generate unicode strings without control chars and escape quotes and backslashes manually.
    def json_string():
        # generate unicode strings without control chars or quotes/backslash
        base = st.text(
            alphabet=(
                chr(i)
                for i in range(0x20, 0xD800)
                if chr(i) not in ['"', '\\']
            ),
            min_size=0,
            max_size=20,
        )
        # randomly insert escapes for \, ", \b, \f, \n, \r, \t, \uXXXX
        # but to keep it simple, just escape " and \ manually
        @st.composite
        def escaped_string(draw):
            s = draw(base)
            # escape backslash and quote
            s = s.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{s}"'
        return escaped_string()

    json_string = json_string()

    # Recursive JSON values
    # Use st.recursive to build obj and arr with bounded depth and size
    # We produce strings (already quoted), numbers, literals, objects, arrays

    # Forward declare value strategy
    # We'll build value as a recursive strategy below

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string,
        json_number,
        json_true,
        json_false,
        json_null,
    )

    # Composite for pair: STRING ':' value
    @st.composite
    def pair(draw, value_strat):
        key = draw(json_string)
        val = draw(value_strat)
        return f"{key}:{val}"

    # Recursive value strategy
    def json_value():
        # Use recursive to build arrays and objects from base_values
        return st.recursive(
            base_values,
            lambda children: st.one_of(
                # object: '{' pair (',' pair)* '}' or '{}'
                st.builds(
                    lambda pairs: "{" + ",".join(pairs) + "}",
                    st.lists(pair(children), max_size=4),
                ),
                st.just("{}"),
                # array: '[' value (',' value)* ']' or '[]'
                st.builds(
                    lambda vals: "[" + ",".join(vals) + "]",
                    st.lists(children, max_size=4),
                ),
                st.just("[]"),
            ),
            max_leaves=10,
        )

    val = draw(json_value())
    # Return as bytes
    return val.encode("utf-8")