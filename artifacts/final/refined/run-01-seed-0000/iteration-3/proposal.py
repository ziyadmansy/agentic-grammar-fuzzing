from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly matching JSON string content with escapes
    # We'll generate Python strings and then encode as JSON strings.
    # To keep near-valid cases, allow some control chars but mostly safe.
    def json_string():
        # Characters allowed inside JSON strings (excluding control chars and quotes/backslash)
        safe_chars = (
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # Escapes: \", \\, \b, \f, \n, \r, \t, \uXXXX
        # We'll generate strings with some escapes by mixing safe chars and escapes.
        # To keep it simple, generate Python strings and then json.dumps them.
        # But since we cannot import json, we manually produce a valid JSON string:
        # We'll generate a string and then escape quotes and backslashes.
        s = draw(st.text(safe_chars, min_size=0, max_size=20))
        # Escape backslash and quotes
        s_escaped = s.replace('\\', '\\\\').replace('"', '\\"')
        # Also replace control chars with escapes
        s_escaped = (
            s_escaped.replace('\b', '\\b')
            .replace('\f', '\\f')
            .replace('\n', '\\n')
            .replace('\r', '\\r')
            .replace('\t', '\\t')
        )
        return f'"{s_escaped}"'

    # NUMBER: generate numbers as strings matching JSON number grammar
    def json_number():
        # Generate a float or int and convert to string matching JSON number format
        # We'll generate numbers with optional exponent and decimal part
        # Use hypothesis floats but restrict to finite numbers
        n = draw(
            st.one_of(
                st.integers(min_value=-10**6, max_value=10**6),
                st.floats(
                    allow_infinity=False,
                    allow_nan=False,
                    width=32,
                    min_value=-1e6,
                    max_value=1e6,
                ),
            )
        )
        # Format number to JSON number string
        if isinstance(n, int):
            return str(n)
        else:
            # Format float with minimal representation
            s = format(n, '.15g')
            # Ensure exponent uses E or e with optional +/-
            # format already does this correctly
            return s

    # Recursive JSON value generator
    # To keep recursion bounded, limit max_depth
    max_depth = 4

    def json_value_strategy(depth=0):
        base = st.one_of(
            st.deferred(json_string),
            st.deferred(json_number),
            json_null,
            json_true,
            json_false,
        )
        if depth >= max_depth:
            return base
        else:
            # Compose object and array recursively
            obj_strategy = st.dictionaries(
                keys=st.deferred(json_string).map(lambda s: s[1:-1]),  # strip quotes for keys
                values=st.deferred(lambda: json_value_strategy(depth + 1)),
                min_size=0,
                max_size=3,
            ).map(
                lambda d: (
                    "{" + ",".join(f'"{k}":{v}' for k, v in d.items()) + "}"
                    if d else "{}"
                )
            )
            arr_strategy = st.lists(
                st.deferred(lambda: json_value_strategy(depth + 1)),
                min_size=0,
                max_size=3,
            ).map(
                lambda lst: "[" + ",".join(lst) + "]"
                if lst else "[]"
            )
            return st.one_of(base, obj_strategy, arr_strategy)

    # Draw a JSON value string
    json_str = draw(json_value_strategy())

    # Return as bytes
    return json_str.encode("utf-8")