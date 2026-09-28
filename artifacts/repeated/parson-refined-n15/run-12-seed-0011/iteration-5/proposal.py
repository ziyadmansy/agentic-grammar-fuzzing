from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Base strategies for JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: use Hypothesis built-in string with safe codepoints and escape quotes/backslashes
    # We'll generate strings without control chars and escape quotes/backslashes manually
    def json_string():
        # Generate unicode strings excluding control chars and quotes/backslash
        # We'll allow safe codepoints except " and \, which we escape
        s = draw(st.text(
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            ),
            max_size=20,
        ))
        # Escape backslash and quote
        s_escaped = s.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{s_escaped}"'

    json_string_st = st.deferred(lambda: st.builds(json_string))

    # NUMBER strategy: use Hypothesis floats and ints, then convert to JSON number string
    def json_number():
        # Draw a float or int in a reasonable range
        n = draw(st.one_of(
            st.integers(min_value=-1_000_000, max_value=1_000_000),
            st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
        ))
        # Format as JSON number string
        if isinstance(n, int):
            return str(n)
        else:
            # Use repr to get a JSON-compatible float string (no inf/nan)
            s = repr(n)
            # Ensure decimal point or exponent present for floats
            if 'e' not in s and '.' not in s:
                s += '.0'
            return s

    json_number_st = st.deferred(lambda: st.builds(json_number))

    # Recursive JSON value strategy
    def json_value():
        return st.recursive(
            st.one_of(
                json_string_st,
                json_number_st,
                json_true,
                json_false,
                json_null,
            ),
            lambda children: st.one_of(
                # Object: { pair (, pair)* } or {}
                st.builds(
                    lambda pairs: "{" + ",".join(pairs) + "}",
                    st.lists(
                        st.tuples(
                            # STRING key
                            json_string_st,
                            # value
                            children,
                        ).map(lambda kv: f"{kv[0]}:{kv[1]}"),
                        max_size=3,
                    ),
                ),
                st.just("{}"),
                # Array: [ value (, value)* ] or []
                st.builds(
                    lambda values: "[" + ",".join(values) + "]",
                    st.lists(children, max_size=4),
                ),
                st.just("[]"),
            ),
            max_leaves=10,
        )

    # Draw the full JSON text and encode as bytes
    json_text = draw(json_value())
    return json_text.encode("utf-8")