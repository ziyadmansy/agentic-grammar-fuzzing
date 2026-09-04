from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING: roughly matching grammar, with safe codepoints and escapes
    # We'll generate Python strings and then json.dumps them to ensure correctness,
    # but since we must return bytes, we'll build strings and encode at the end.
    # To keep near-valid cases, allow some invalid escapes by mixing safe and escaped chars.
    # However, Hypothesis has a built-in json module strategy, but we must implement our own.

    # We'll define a string strategy that generates strings with safe codepoints and some escapes.
    # To keep it simple, generate unicode strings excluding control chars, then encode with json.dumps.

    import json

    # STRING strategy: generate Python strings with safe chars and some escapes
    # We'll generate strings with codepoints >= 0x20 except '"' and '\\'
    # plus some escaped sequences.
    safe_chars = st.characters(
        blacklist_characters=['"', '\\'],
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    )
    # To allow some escapes, we can insert backslash followed by one of ["\\/bfnrtu]
    # but to keep it simple, generate strings and then json.dumps them for correctness.

    # NUMBER strategy: generate floats and ints matching JSON number grammar
    # We'll generate Python floats and ints and convert to str without trailing '+' in exponents.
    def json_number():
        # Generate int or float, then convert to JSON number string
        # Use floats with limited precision to avoid weird formatting
        n = draw(st.one_of(
            st.integers(min_value=-10**6, max_value=10**6),
            st.floats(allow_nan=False, allow_infinity=False, width=32),
        ))
        # Format number to JSON number string
        if isinstance(n, int):
            return str(n)
        else:
            # Format float with repr, remove trailing zeros in fraction
            s = format(n, '.15g')
            # Ensure exponent uses E or e with optional sign but no plus sign
            # Python uses 'e' with optional '+' sign, JSON allows both
            # We'll keep Python's format but remove '+' in exponent if present
            if 'e+' in s:
                s = s.replace('e+', 'e')
            elif 'E+' in s:
                s = s.replace('E+', 'E')
            return s

    # Recursive value strategy
    def json_value():
        # Base: string, number, true, false, null
        base = st.one_of(
            st.builds(lambda s: json.dumps(s), st.text(min_size=0, max_size=20, alphabet=safe_chars)),
            st.builds(json_number),
            json_true,
            json_false,
            json_null,
        )
        # Recursive: object or array
        return st.recursive(
            base,
            lambda children: st.one_of(
                # object: { pair (, pair)* } or {}
                st.builds(
                    lambda pairs: "{" + ",".join(pairs) + "}",
                    st.lists(
                        st.tuples(
                            st.builds(lambda s: json.dumps(s), st.text(min_size=1, max_size=10, alphabet=safe_chars)),
                            children,
                        ),
                        max_size=5,
                    ).map(lambda pairs: [f"{k}:{v}" for k, v in pairs]),
                ),
                # array: [ value (, value)* ] or []
                st.builds(
                    lambda values: "[" + ",".join(values) + "]",
                    st.lists(children, max_size=5),
                ),
            ),
            max_leaves=10,
        )

    # Compose full JSON with EOF (implicit)
    json_str = draw(json_value())
    return json_str.encode("utf-8")