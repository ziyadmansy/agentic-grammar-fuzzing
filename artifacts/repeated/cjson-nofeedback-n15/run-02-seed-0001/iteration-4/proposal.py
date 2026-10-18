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
        # safe characters exclude control chars and backslash, quote
        safe_chars = (
            st.characters(
                blacklist_characters=['"', '\\'],
                min_codepoint=0x20,
                max_codepoint=0x10FFFF,
            )
        )
        # generate text of length 0 to 20
        s = draw(st.text(safe_chars, min_size=0, max_size=20))
        # escape backslash and quote
        s_escaped = s.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{s_escaped}"'

    json_string_st = st.deferred(lambda: st.builds(lambda s: s, st.just(json_string())))

    # NUMBER strategy: generate numbers as strings matching JSON number grammar
    # Use floats and ints converted to strings, but keep them simple
    def json_number():
        # Generate int or float, then convert to JSON number string
        # Limit magnitude to avoid huge numbers
        n = draw(
            st.one_of(
                st.integers(min_value=-10**6, max_value=10**6),
                st.floats(
                    allow_nan=False,
                    allow_infinity=False,
                    width=32,
                    min_value=-1e6,
                    max_value=1e6,
                ),
            )
        )
        # Format number as JSON number string
        if isinstance(n, int):
            return str(n)
        else:
            # Format float with minimal representation
            s = format(n, '.15g')
            # Ensure decimal point or exponent to distinguish from int
            if '.' not in s and 'e' not in s and 'E' not in s:
                s += '.0'
            return s

    json_number_st = st.deferred(lambda: st.builds(lambda s: s, st.just(json_number())))

    # Recursive JSON value strategy
    # We'll define a recursive strategy that can produce:
    # STRING, NUMBER, obj, arr, true, false, null

    # Forward declaration for recursion
    json_value = st.deferred(lambda: json_value_inner)

    # Object: { pair (, pair)* } or {}
    # pair: STRING : value
    def json_pair():
        key = draw(json_string_st)
        val = draw(json_value)
        return f"{key}:{val}"

    def json_object():
        # 0 to 4 pairs to keep size bounded
        n_pairs = draw(st.integers(min_value=0, max_value=4))
        if n_pairs == 0:
            return "{}"
        pairs = []
        for _ in range(n_pairs):
            pairs.append(draw(json_pair()))
        return "{" + ",".join(pairs) + "}"

    # Array: [ value (, value)* ] or []
    def json_array():
        n_vals = draw(st.integers(min_value=0, max_value=4))
        if n_vals == 0:
            return "[]"
        vals = []
        for _ in range(n_vals):
            vals.append(draw(json_value))
        return "[" + ",".join(vals) + "]"

    # Compose the recursive strategy
    json_value_inner = st.recursive(
        st.one_of(
            json_string_st,
            json_number_st,
            json_null,
            json_true,
            json_false,
        ),
        lambda children: st.one_of(
            st.builds(lambda o: o, st.deferred(lambda: st.just(json_object()))),
            st.builds(lambda a: a, st.deferred(lambda: st.just(json_array()))),
        ),
        max_leaves=10,
    )

    # Because json_object and json_array depend on json_value, we must redefine them here
    # using draw inside a composite to avoid recursion issues

    @st.composite
    def json_value(draw):
        base = draw(
            st.one_of(
                json_string_st,
                json_number_st,
                json_null,
                json_true,
                json_false,
            )
        )
        # With some probability, recurse into object or array
        if draw(st.booleans()):
            # Choose object or array
            if draw(st.booleans()):
                # object
                n_pairs = draw(st.integers(min_value=0, max_value=4))
                if n_pairs == 0:
                    return "{}"
                pairs = []
                for _ in range(n_pairs):
                    key = draw(json_string_st)
                    val = draw(json_value)
                    pairs.append(f"{key}:{val}")
                return "{" + ",".join(pairs) + "}"
            else:
                # array
                n_vals = draw(st.integers(min_value=0, max_value=4))
                if n_vals == 0:
                    return "[]"
                vals = [draw(json_value) for _ in range(n_vals)]
                return "[" + ",".join(vals) + "]"
        else:
            return base

    # Compose final JSON text: value + EOF
    json_text = json_value

    # Draw the JSON text and encode as bytes
    s = draw(json_text)
    return s.encode("utf-8")