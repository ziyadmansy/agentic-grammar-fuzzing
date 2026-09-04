from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then JSON-encode them to ensure correctness.
    # But since we cannot import json module or use eval/exec, we build strings manually.
    # We'll generate strings with safe unicode codepoints excluding control chars and quotes/backslash.
    # Then escape quotes, backslash, and control chars manually.

    def json_escape(s: str) -> str:
        # Escape backslash and quotes and control chars
        res = []
        for c in s:
            o = ord(c)
            if c == '"':
                res.append('\\"')
            elif c == '\\':
                res.append('\\\\')
            elif c == '\b':
                res.append('\\b')
            elif c == '\f':
                res.append('\\f')
            elif c == '\n':
                res.append('\\n')
            elif c == '\r':
                res.append('\\r')
            elif c == '\t':
                res.append('\\t')
            elif 0 <= o <= 0x1F:
                res.append(f'\\u{o:04x}')
            else:
                res.append(c)
        return '"' + ''.join(res) + '"'

    # Generate strings of length up to 20 with safe codepoints (excluding control chars, quote, backslash)
    safe_chars = st.characters(
        blacklist_characters=['"', '\\'],
        blacklist_categories=('Cc',),  # control chars
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    )
    json_string = st.text(safe_chars, max_size=20).map(json_escape)

    # NUMBER strategy: generate numbers as strings matching the grammar
    # We'll generate floats and ints and format them accordingly
    def number_to_json(n):
        # Format number as JSON number string
        # Use repr for floats, str for ints
        if isinstance(n, int):
            return str(n)
        else:
            # Use repr to get exponent if needed
            s = repr(n)
            # repr can produce 'inf', 'nan' - avoid those
            if s in ('inf', '-inf', 'nan', '-nan'):
                return "0"
            return s

    json_number = st.one_of(
        st.integers(min_value=-10**6, max_value=10**6).map(number_to_json),
        st.floats(
            allow_infinity=False,
            allow_nan=False,
            width=32,
            min_value=-1e6,
            max_value=1e6,
        ).map(number_to_json),
    )

    # Recursive JSON value strategy
    # We'll use st.recursive to build nested objects and arrays with bounded depth and size

    # Forward declare value strategy for recursion
    # value = STRING | NUMBER | obj | arr | true | false | null

    # We'll define obj and arr inside the recursive function

    def json_value():
        base = st.one_of(
            json_string,
            json_number,
            json_null,
            json_true,
            json_false,
        )

        # Recursive containers
        def obj_strategy():
            # pair: STRING ':' value
            pair = st.tuples(json_string, json_value()).map(lambda p: p[0] + ":" + p[1])
            # object: '{' pair (',' pair)* '}' or '{}'
            # limit pairs to max 5 to keep size bounded
            pairs = st.lists(pair, max_size=5)
            return pairs.map(lambda ps: "{" + ",".join(ps) + "}" if ps else "{}")

        def arr_strategy():
            # array: '[' value (',' value)* ']' or '[]'
            vals = st.lists(json_value(), max_size=5)
            return vals.map(lambda vs: "[" + ",".join(vs) + "]" if vs else "[]")

        return st.recursive(
            base,
            lambda children: st.one_of(obj_strategy(), arr_strategy()),
            max_leaves=10,
        )

    # Compose full JSON text: value EOF
    json_text = json_value().map(lambda s: s)

    # Draw one example and encode as UTF-8 bytes
    s = draw(json_text)
    return s.encode("utf-8")