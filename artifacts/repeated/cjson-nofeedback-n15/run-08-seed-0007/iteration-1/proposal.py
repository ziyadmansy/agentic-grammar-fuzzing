from hypothesis import strategies as st

@st.composite
def generated_json(draw) -> bytes:
    # Basic JSON primitives
    json_null = st.just("null")
    json_true = st.just("true")
    json_false = st.just("false")

    # STRING strategy: simple escaped strings, avoiding control chars
    def json_string():
        # SAFECODEPOINT ~["\\\u0000-\u001F], roughly printable except backslash and quote
        # We'll generate unicode strings excluding control chars and backslash, quote
        # Then escape some chars to produce valid JSON strings
        # To keep it simple, generate ascii printable except backslash and quote
        safe_chars = st.characters(
            blacklist_characters=['\\', '"'],
            min_codepoint=0x20,
            max_codepoint=0x7E,
        )
        # Compose string with length 0..20
        s = st.text(safe_chars, max_size=20)

        def escape_json_string(s):
            # Escape backslash and quote, and control chars if any (should be none)
            # Also escape common escapes for safety
            s = s.replace('\\', '\\\\').replace('"', '\\"')
            # Also escape control chars if any (unlikely)
            s = s.replace('\b', '\\b').replace('\f', '\\f').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
            return f'"{s}"'

        return s.map(escape_json_string)

    # NUMBER strategy: follow grammar '-'? INT ('.' [0-9]+)? EXP?
    def json_number():
        # INT: '0' or non-zero digit followed by digits
        # We'll generate int part as int, then format accordingly
        # EXP: optional e/E with optional +/- and digits
        # We'll generate floats and ints and format them accordingly

        # Generate a float or int in a reasonable range
        # To keep near-valid, generate floats with optional exponent
        # We'll generate a float and format it to JSON number string

        # Generate sign
        sign = st.sampled_from(["", "-"])
        # Generate integer part: '0' or non-zero digit followed by digits
        int_part = st.one_of(
            st.just("0"),
            st.integers(min_value=1, max_value=10**6).map(str)
        )
        # Fractional part optional
        frac_part = st.one_of(
            st.just(""),
            st.tuples(st.just("."), st.integers(min_value=0, max_value=10**6).map(str)).map(lambda t: t[0] + t[1])
        )
        # Exponent optional
        exp_part = st.one_of(
            st.just(""),
            st.tuples(
                st.sampled_from(["e", "E"]),
                st.sampled_from(["", "+", "-"]),
                st.integers(min_value=0, max_value=1000).map(str)
            ).map(lambda t: t[0] + t[1] + t[2])
        )
        return st.tuples(sign, int_part, frac_part, exp_part).map(lambda t: "".join(t))

    # Forward declaration for recursive value
    # We'll define value recursively below

    # Compose value strategy recursively
    # Use st.recursive to keep size bounded

    # Base values: string, number, true, false, null
    base_values = st.one_of(
        json_string(),
        json_number(),
        json_true,
        json_false,
        json_null,
    )

    # Recursive containers: obj and arr
    # We'll define obj and arr as composites to control size and structure

    @st.composite
    def json_value(draw):
        # Use st.recursive to build nested structures with bounded depth
        # Compose base values and recursive containers

        # Define recursive containers here to avoid forward reference issues

        # obj: '{' pair (',' pair)* '}' | '{}'
        # pair: STRING ':' value

        # arr: '[' value (',' value)* ']' | '[]'

        # We define pair as STRING ':' value string

        # We'll limit number of pairs or elements to max 3 to keep size bounded

        # We'll define value recursively with max depth 3

        def json_obj():
            # Generate 0..3 pairs
            n = draw(st.integers(min_value=0, max_value=3))
            if n == 0:
                return "{}"
            pairs = []
            for _ in range(n):
                key = draw(json_string())
                val = draw(json_value())
                pairs.append(f"{key}:{val}")
            return "{" + ",".join(pairs) + "}"

        def json_arr():
            n = draw(st.integers(min_value=0, max_value=3))
            if n == 0:
                return "[]"
            elements = [draw(json_value()) for _ in range(n)]
            return "[" + ",".join(elements) + "]"

        # Compose recursive strategy with base and containers
        # To avoid infinite recursion, limit depth by controlling calls

        # We'll randomly choose to generate base or container
        choice = draw(st.integers(min_value=0, max_value=4))
        if choice == 0:
            return draw(json_string())
        elif choice == 1:
            return draw(json_number())
        elif choice == 2:
            return draw(json_true)
        elif choice == 3:
            return draw(json_false)
        elif choice == 4:
            # Choose container type
            container_type = draw(st.sampled_from(["obj", "arr"]))
            if container_type == "obj":
                return json_obj()
            else:
                return json_arr()
        else:
            # fallback base
            return draw(base_values)

    # Use json_value as the top-level json
    s = draw(json_value())
    return s.encode("utf-8")