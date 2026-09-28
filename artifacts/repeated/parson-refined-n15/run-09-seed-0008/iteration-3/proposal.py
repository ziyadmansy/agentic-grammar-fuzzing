from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")
    json_number = st.from_regex(
        r'-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?',
        fullmatch=True,
        max_size=20,
    )
    # STRING: roughly matching the grammar, allowing safe codepoints and escapes
    # We'll generate strings and then escape them properly.
    # To keep near-valid cases, sometimes produce invalid escapes.
    def json_string():
        # Generate a unicode string with codepoints excluding control chars and quotes/backslash
        # Then escape it properly or sometimes produce near-valid escapes.
        # We'll generate a string and then encode it with JSON escaping.
        # Use a small helper to produce near-valid escapes by sometimes inserting invalid escape sequences.
        base_str = st.text(
            alphabet=(
                # safe codepoints: exclude control chars (0x00-0x1F), quote (0x22), backslash (0x5C)
                # We'll allow all printable except quote and backslash
                # Unicode range: 0x20-0x10FFFF except 0x22 and 0x5C
                # Hypothesis text alphabet doesn't support exclusion easily, so filter after generation.
                # We'll generate from a wide range and filter.
                # To keep it simple, generate ascii letters, digits, space, and some punctuation except " and \
                "abcdefghijklmnopqrstuvwxyz"
                "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                "0123456789"
                " !#$%&'()*+,-./:;<=>?@[]^_`{|}~"
            ),
            min_size=0,
            max_size=30,
        )
        s = draw(base_str)
        # Escape string according to JSON rules, but sometimes produce near-valid escapes:
        # 90% valid escapes, 10% invalid escape sequences.
        import random
        def escape_json_string(s):
            res = ['"']
            i = 0
            while i < len(s):
                c = s[i]
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
                elif ord(c) < 0x20:
                    # control char, escape as unicode
                    res.append('\\u%04x' % ord(c))
                else:
                    res.append(c)
                i += 1
            res.append('"')
            return ''.join(res)

        # 10% chance to insert an invalid escape sequence randomly
        if draw(st.booleans()) and len(s) > 0:
            # Insert an invalid escape sequence at a random position
            pos = draw(st.integers(min_value=0, max_value=len(s) - 1))
            # Replace character at pos with a backslash + invalid escape char
            invalid_escapes = ['\\x', '\\z', '\\q', '\\uZZZZ']
            chosen = draw(st.sampled_from(invalid_escapes))
            s = s[:pos] + chosen + s[pos + 1 :]
            # Wrap in quotes but do not escape further (to keep near-valid)
            return s.encode("utf-8")
        else:
            return escape_json_string(s).encode("utf-8")

    json_string_st = st.deferred(json_string)

    # Recursive JSON values
    # Use st.recursive to keep size bounded and produce valid or near-valid JSON structures
    def json_value():
        # Base cases: string, number, true, false, null
        base = st.one_of(
            json_string_st,
            json_number,
            json_true,
            json_false,
            json_null,
        )

        # Recursive cases: object and array
        # We'll produce bytes directly for these, so we need to combine bytes parts
        def json_object():
            # Generate 0 to 5 pairs
            # Each pair: string : value
            # We'll generate keys as strings (bytes) and values as bytes
            # Then join with commas and wrap with braces
            pairs = st.lists(
                st.tuples(json_string_st, json_value()),
                max_size=5,
                unique_by=lambda p: p[0],  # unique keys by string bytes
            )

            def render_obj(pairs):
                if not pairs:
                    return b"{}"
                parts = []
                for k, v in pairs:
                    parts.append(k + b":" + v)
                return b"{" + b",".join(parts) + b"}"

            return pairs.map(render_obj)

        def json_array():
            # Generate 0 to 5 values
            values = st.lists(json_value(), max_size=5)

            def render_arr(values):
                if not values:
                    return b"[]"
                return b"[" + b",".join(values) + b"]"

            return values.map(render_arr)

        return st.recursive(
            base,
            lambda children: st.one_of(json_object(), json_array()),
            max_leaves=10,
        )

    # Generate full JSON and append EOF (empty)
    # The grammar expects json : value EOF
    # We'll produce only the value bytes (no trailing data)
    return draw(json_value())