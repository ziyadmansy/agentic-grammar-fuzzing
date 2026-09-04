from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly matching the grammar, with escapes and safe codepoints
    # We'll generate Python strings and then json-encode them to ensure correctness.
    # But since we can't import json or use eval, we build a safe string strategy:
    # We'll allow ASCII printable except control chars and backslash/quote,
    # plus some escapes.
    # To keep it simple, generate strings of safe unicode codepoints excluding control chars and quotes/backslash.
    # Then escape quotes and backslashes manually.

    def escape_string(s: str) -> str:
        # Escape backslash and quote, and control chars as \uXXXX
        res = []
        for c in s:
            o = ord(c)
            if c == '"':
                res.append('\\"')
            elif c == '\\':
                res.append('\\\\')
            elif 0x00 <= o <= 0x1F:
                res.append(f"\\u{o:04x}")
            else:
                res.append(c)
        return '"' + "".join(res) + '"'

    safe_char = st.characters(
        blacklist_characters=['"', '\\'],
        blacklist_categories=('Cc',)  # control chars
    )
    json_string = st.text(safe_char, min_size=0, max_size=20).map(escape_string)

    # NUMBER: generate floats and ints as strings matching the grammar
    # We'll generate numbers as Python floats or ints and then format them to JSON number strings
    def format_number(n):
        # Format int or float to JSON number string
        if isinstance(n, int):
            return str(n)
        else:
            # Use repr to get a compact float representation
            s = repr(n)
            # Ensure exponent uses E or e with optional +/-
            # repr uses e, which is fine
            return s

    json_number = st.one_of(
        st.integers(min_value=-10**6, max_value=10**6),
        st.floats(allow_infinity=False, allow_nan=False, width=32, min_value=-1e6, max_value=1e6)
    ).map(format_number)

    # Forward declaration for recursive structures
    # We'll use st.recursive to build obj and arr

    # Pair: STRING ':' value
    @st.composite
    def pair(draw, value_strat):
        k = draw(json_string)
        v = draw(value_strat)
        return f"{k}:{v}"

    # Recursive value strategy
    def json_value():
        # Base values
        base = st.one_of(
            json_string,
            json_number,
            json_null,
            json_true,
            json_false,
        )
        # Recursive structures: obj and arr
        # Use recursive to limit depth and size
        return st.recursive(
            base,
            lambda children: st.one_of(
                # obj: '{' pair (',' pair)* '}' or '{}'
                st.lists(pair(children), min_size=0, max_size=5).map(
                    lambda pairs: "{" + ",".join(pairs) + "}"
                ),
                # arr: '[' value (',' value)* ']' or '[]'
                st.lists(children, min_size=0, max_size=5).map(
                    lambda vals: "[" + ",".join(vals) + "]"
                ),
            ),
            max_leaves=10,
        )

    val = draw(json_value())
    # The grammar requires json : value EOF, so val is the whole JSON text
    return val.encode("utf-8")