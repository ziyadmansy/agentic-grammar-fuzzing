from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: produce valid JSON strings with escapes and safe codepoints
    # We'll generate Python strings and then encode them as JSON strings.
    # To keep it simple, use st.text with safe characters and escape quotes/backslashes.
    def json_string():
        # safe codepoints exclude control chars and quotes/backslash
        safe_chars = (
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # Compose string with length limit to keep size bounded
        s = draw(st.text(safe_chars, min_size=0, max_size=20))
        # Escape backslash and quotes
        s_escaped = s.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{s_escaped}"'

    json_string_st = st.deferred(lambda: st.builds(lambda s: s, st.just(json_string())))

    # NUMBER strategy: produce valid JSON numbers as strings
    # Use Hypothesis floats and ints, then format as JSON number strings
    def json_number():
        # Generate int or float as string
        # Limit floats to finite and reasonable range
        n = draw(
            st.one_of(
                st.integers(min_value=-10**6, max_value=10**6).map(str),
                st.floats(
                    allow_nan=False,
                    allow_infinity=False,
                    width=32,
                    min_value=-1e6,
                    max_value=1e6,
                ).map(lambda f: format(f, '.6g')),
            )
        )
        return n

    json_number_st = st.deferred(lambda: st.builds(lambda n: n, st.just(json_number())))

    # Recursive JSON value strategy
    # We'll define a recursive strategy for value that can be string, number, obj, arr, true, false, null
    # Use st.recursive with max_leaves to keep size bounded

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        st.deferred(lambda: st.just(json_string())),
        st.deferred(lambda: st.just(json_number())),
        json_true,
        json_false,
        json_null,
    )

    # Forward declarations for obj and arr
    # obj: '{' pair (',' pair)* '}' or '{}'
    # pair: STRING ':' value
    # arr: '[' value (',' value)* ']' or '[]'

    # We'll define pair and obj/arr inside the recursive strategy

    def json_value():
        # Use recursive to build nested objects and arrays
        def pair():
            # pair: STRING ':' value
            k = draw(json_string_st)
            v = draw(value_st)
            return f"{k}:{v}"

        def obj():
            # empty or one or more pairs separated by ','
            pairs = draw(
                st.lists(
                    st.deferred(lambda: pair()),
                    min_size=0,
                    max_size=3,
                )
            )
            if len(pairs) == 0:
                return "{}"
            else:
                return "{" + ",".join(pairs) + "}"

        def arr():
            # empty or one or more values separated by ','
            values = draw(
                st.lists(
                    st.deferred(lambda: value_st),
                    min_size=0,
                    max_size=3,
                )
            )
            if len(values) == 0:
                return "[]"
            else:
                return "[" + ",".join(values) + "]"

        # Compose the recursive value strategy
        # We'll use st.recursive to define value_st below
        # But here we just return a placeholder to satisfy draw calls
        return draw(value_st)

    # Define value_st recursively
    # Because we need to use draw inside pair/obj/arr, we define a composite strategy for value_st
    @st.composite
    def value_st(draw):
        # base values or recursive objects/arrays
        base = draw(base_values)
        # With some probability, build obj or arr
        # To keep size bounded, limit recursion depth by controlling max_leaves in recursive
        # But since we use composite, we control recursion by limiting max_size of lists
        choice = draw(
            st.one_of(
                st.just(base),
                st.just(obj()),
                st.just(arr()),
            )
        )
        return choice

    # Now generate top-level JSON text and encode as bytes
    json_text = draw(value_st())
    # Append EOF is implicit, so just encode
    return json_text.encode("utf-8")